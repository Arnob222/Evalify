from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count
from django.core.files.base import ContentFile
from collections import defaultdict
import json
import base64
import uuid
from datetime import date, timedelta
from django.utils import timezone
from .models import (User, Course, CLO, PLO, Assessment, Question, SubQuestion, SubQuestionGrade,
                     Enrollment, Submission, QuestionGrade, Announcement, StudyMaterial, Notification,
                     CLOActionPlan, PLOActionPlan)
from .notifications import (notify_grade_released, notify_new_assignment, notify_new_material, notify_announcement)
from .grace_period import check_submission_window, apply_late_deduction, recalculate_final_score


#Home Redirect 
def home(request):
    if not request.user.is_authenticated:
        return render(request, 'homepage.html')
    if request.user.role == 'faculty' or request.user.is_superuser:
        return redirect('faculty_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'admin':
        return redirect('admin_dashboard')
    return render(request, 'homepage.html')


#Auth 

def sign_in_html(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            if user and user.is_active:
                login(request, user)
                return redirect('home')
        except User.DoesNotExist:
            pass
        return render(request, 'sign_in.html', {'error': 'Invalid email or password.'})
    return render(request, 'sign_in.html')


def sign_up_html(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'student')

        # Basic validations
        if not full_name or not email or not password:
            return render(request, 'sign_up.html', {'error': 'All fields are required.'})
        if len(password) < 8:
            return render(request, 'sign_up.html', {'error': 'Password must be at least 8 characters.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'sign_up.html', {'error': 'Email already registered.'})

        # --- EMAIL DOMAIN VALIDATION BASED ON ROLE ---
        import re
        if role == 'student':
            # Must be digits@uap-bd.edu
            if not re.match(r'^\d+@uap-bd\.edu$', email):
                return render(request, 'sign_up.html', {'error': 'Student email must be digits@uap-bd.edu (e.g., 20241001@uap-bd.edu).'})
        elif role in ('faculty', 'admin'):
            # Must be name (letters/dots/underscores)@uap-bd.edu or admin@uap-bd.edu
            if not re.match(r'^[A-Za-z][A-Za-z0-9._]*@uap-bd\.edu$', email):
                return render(request, 'sign_up.html', {'error': 'Faculty email must be name@uap-bd.edu (e.g., john.doe@uap-bd.edu).'})
        else:
            return render(request, 'sign_up.html', {'error': 'Invalid role selected.'})

        # Generate unique username from email local part
        username = email.split('@')[0]
        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1

        # Create user (your custom User model has `role` and `full_name` fields)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role=role,
        )
        return redirect('/signin/?registered=1')
    return render(request, 'sign_up.html')


def sign_out(request):
    logout(request)
    return redirect('sign_in_html')


# Faculty Required

def faculty_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('sign_in_html')
        if request.user.role not in ('faculty', 'admin') and not request.user.is_superuser:
            return redirect('student_dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# Student Required 

def student_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('sign_in_html')
        if request.user.role not in ('student', 'admin') and not request.user.is_superuser:
            return redirect('faculty_dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper



#Faculty Views

@faculty_required
def faculty_dashboard(request):
    now = timezone.now()
    courses = Course.objects.filter(faculty=request.user).prefetch_related('enrollments', 'clos')
    assessments = Assessment.objects.filter(course__in=courses)
    pending_subs = Submission.objects.filter(assessment__in=assessments, status='submitted')
    flagged_subs = Submission.objects.filter(assessment__in=assessments, status='flagged')
    graded_subs  = Submission.objects.filter(assessment__in=assessments, status='graded')
    total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()

    recent_submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment', 'assessment__course').order_by('-submitted_at')[:6]

    announcements = Announcement.objects.filter(course__in=courses).order_by('-created_at')[:4]

    upcoming = assessments.filter(
        status='published', due_date__gte=now, due_date__lte=now + timedelta(days=7)
    ).select_related('course').order_by('due_date')

    courses_stats = []
    for course in courses:
        course.enrolled_count  = course.enrollments.count()
        course.pending_grading = pending_subs.filter(assessment__course=course).count()
        courses_stats.append(course)

    return render(request, 'faculty/dashboard.html', {
        'courses': courses_stats,
        'assessments_count': assessments.count(),
        'pending_count': pending_subs.count(),
        'flagged_count': flagged_subs.count(),
        'graded_count': graded_subs.count(),
        'total_students': total_students,
        'recent_submissions': recent_submissions,
        'announcements': announcements,
        'upcoming': upcoming,
    })


@faculty_required
def faculty_enrolled_students(request):
    courses = Course.objects.filter(faculty=request.user).prefetch_related(
        'enrollments', 'enrollments__student'
    ).order_by('code')
    search = request.GET.get('q', '').strip()
    course_filter = request.GET.get('course', '')
    all_enrollments = []
    for course in courses:
        for enroll in course.enrollments.all():
            student = enroll.student
            if search and search.lower() not in (student.full_name or '').lower() and search.lower() not in student.username.lower():
                continue
            if course_filter and str(course.id) != course_filter:
                continue
            all_enrollments.append({'enrollment': enroll, 'student': student, 'course': course})
    return render(request, 'faculty/enrolled_students.html', {
        'courses': courses,
        'all_enrollments': all_enrollments,
        'search': search,
        'course_filter': course_filter,
        'total_count': len(all_enrollments),
    })


@faculty_required
def faculty_courses(request):
    courses = Course.objects.filter(faculty=request.user).prefetch_related(
        'clos', 'clos__plos', 'enrollments', 'enrollments__student'
    )
    for course in courses:
        plo_ids = set()
        for clo in course.clos.all():
            for plo in clo.plos.all():
                plo_ids.add(plo.id)
        course.plo_count = len(plo_ids)

    # All unique enrolled students across all courses for the global students section
    all_enrollments = Enrollment.objects.filter(
        course__faculty=request.user
    ).select_related('student', 'course').order_by('student__full_name', 'course__code')

    plos = PLO.objects.all()
    return render(request, 'faculty/courses.html', {
        'courses': courses,
        'plos': plos,
        'all_enrollments': all_enrollments,
    })
 


@faculty_required
def add_course(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = Course.objects.create(
            code=data['code'], name=data['name'],
            description=data.get('description', ''),
            credit_hours=int(data.get('credit_hours', 3)),
            semester=data.get('semester', 'Fall 2025'),
            faculty=request.user
        )
        return JsonResponse({'success': True, 'id': course.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def add_clo(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        count = course.clos.count() + 1
        clo = CLO.objects.create(
            course=course, code=f"CLO{count}",
            description=data['description'],
            bloom_level=data['bloom_level']
        )
        if data.get('plo_ids'):
            clo.plos.set(PLO.objects.filter(id__in=data['plo_ids']))
        return JsonResponse({'success': True, 'id': clo.id, 'code': clo.code})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_clo(request, clo_id):
    clo = get_object_or_404(CLO, id=clo_id, course__faculty=request.user)
    clo.delete()
    return JsonResponse({'success': True})


@faculty_required
def get_course_clos(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    clos = list(course.clos.values('id', 'code', 'description', 'bloom_level'))
    return JsonResponse({'clos': clos})


@faculty_required
def add_student_to_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            student = User.objects.get(email=data['email'], role='student')
            Enrollment.objects.get_or_create(student=student, course=course)
            return JsonResponse({'success': True, 'name': student.full_name or student.username})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def remove_student_from_course(request, course_id, student_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method == 'POST':
        Enrollment.objects.filter(student_id=student_id, course=course).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)
def add_students_by_range(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    data = json.loads(request.body)
    try:
        from_id = int(str(data.get('from_id', '')).strip())
        to_id   = int(str(data.get('to_id',   '')).strip())
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Registration IDs must be numbers.'}, status=400)
    if from_id > to_id:
        return JsonResponse({'error': 'From ID must be less than or equal to To ID.'}, status=400)
    if to_id - from_id >= 500:
        return JsonResponse({'error': 'Range too large — maximum 500 students at once.'}, status=400)

    added, already_enrolled, not_found = [], [], []
    for reg_id in range(from_id, to_id + 1):
        email = f'{reg_id}@uap-bd.edu'
        try:
            student = User.objects.get(email=email, role='student')
            _, created = Enrollment.objects.get_or_create(student=student, course=course)
            (added if created else already_enrolled).append(reg_id)
        except User.DoesNotExist:
            not_found.append(reg_id)

    return JsonResponse({
        'success': True,
        'added': len(added),
        'already_enrolled': len(already_enrolled),
        'not_found': len(not_found),
        'not_found_ids': not_found[:30],
    })


@faculty_required
def faculty_assessments(request):
    courses = Course.objects.filter(faculty=request.user)
    assessments = Assessment.objects.filter(course__in=courses).prefetch_related(
        'questions__clos__plos'
    ).order_by('-created_at')
    return render(request, 'faculty/assessments.html', {
        'assessments': assessments, 'courses': courses
    })


@faculty_required
def create_assessment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        assessment = Assessment.objects.create(
            course=course, title=data['title'],
            description=data.get('description', ''),
            assessment_type=data['assessment_type'],
            due_date=data['due_date'], status='published'
        )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            question = Question.objects.create(
                assessment=assessment, order=i,
                text=q['text'], max_marks=int(q['max_marks'])
            )
            if q.get('clo_ids'):
                question.clos.set(CLO.objects.filter(id__in=q['clo_ids']))
            total += int(q['max_marks'])
        Assessment.objects.filter(pk=assessment.pk).update(total_marks=total)
        return JsonResponse({'success': True, 'id': assessment.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_grading(request):
    courses = Course.objects.filter(faculty=request.user)

    course_id = request.GET.get('course')
    if not course_id:
        # Level 1 — course cards with submission counts
        course_cards = []
        for c in courses:
            assessments = Assessment.objects.filter(course=c)
            subs = Submission.objects.filter(assessment__in=assessments)
            total   = subs.count()
            pending = subs.filter(status='submitted').count()
            graded  = subs.filter(status__in=['graded', 'flagged']).count()
            if total > 0:
                course_cards.append({
                    'course':  c,
                    'total':   total,
                    'pending': pending,
                    'graded':  graded,
                })
        return render(request, 'faculty/grading.html', {
            'course_cards': course_cards,
            'selected_course': None,
        })

    # Level 2 — submissions for selected course
    selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    assessments = Assessment.objects.filter(course=selected_course)
    submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment__course').order_by('-submitted_at')
    return render(request, 'faculty/grading.html', {
        'submissions':     submissions,
        'assessments':     assessments,
        'selected_course': selected_course,
        'pending':         submissions.filter(status='submitted').count(),
        'graded':          submissions.filter(status__in=['graded', 'flagged']).count(),
        'course_cards':    None,
    })


@faculty_required
def get_submission_detail(request, sub_id):
    sub = get_object_or_404(Submission, id=sub_id, assessment__course__faculty=request.user)
    questions = []
    for q in sub.assessment.questions.all().order_by('order'):
        try:
            obtained = QuestionGrade.objects.get(submission=sub, question=q).marks_obtained
        except QuestionGrade.DoesNotExist:
            obtained = 0

        sub_qs = []
        for sq in q.sub_questions.order_by('order'):
            try:
                sq_obtained = SubQuestionGrade.objects.get(submission=sub, sub_question=sq).marks_obtained
            except SubQuestionGrade.DoesNotExist:
                sq_obtained = 0
            sub_qs.append({
                'id': sq.id, 'order': sq.order, 'text': sq.text,
                'image_url': sq.image.url if sq.image else None,
                'max_marks': sq.max_marks, 'obtained': sq_obtained,
                'clos': [{'code': c.code} for c in sq.clos.all()],
                'plos': [{'code': p.code} for p in sq.plos.all()],
            })

        questions.append({
            'id': q.id, 'order': q.order, 'text': q.text,
            'image_url': q.image.url if q.image else None,
            'max_marks': q.max_marks, 'obtained': obtained,
            'clos': [{'code': c.code} for c in q.clos.all()],
            'plos': [{'code': p.code} for p in q.plos.all()],
            'sub_questions': sub_qs,
        })
    file_url = sub.submitted_file.url if sub.submitted_file else None
    file_name = sub.submitted_file.name.split('/')[-1] if sub.submitted_file else None
    return JsonResponse({
        'id': sub.id,
        'student_name': sub.student.full_name or sub.student.username,
        'assessment_title': sub.assessment.title,
        'assessment_type': sub.assessment.assessment_type,
        'total_marks': sub.assessment.total_marks,
        'content': sub.content,
        'file_url': file_url,
        'file_name': file_name,
        'plagiarism': sub.plagiarism_score,
        'ai_content': sub.ai_content_score,
        'status': sub.status,
        'total_score': sub.total_score,
        'feedback': sub.feedback,
        'questions': questions,
    })


@faculty_required
def grade_submission(request, sub_id):
    sub = get_object_or_404(Submission, id=sub_id, assessment__course__faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        total = 0

        # Sub-question grades
        sq_totals = defaultdict(float)  # question_id → accumulated sub marks
        for sqg in data.get('sub_question_grades', []):
            sq = get_object_or_404(SubQuestion, id=sqg['sub_question_id'])
            marks = min(float(sqg['marks']), sq.max_marks)
            SubQuestionGrade.objects.update_or_create(
                submission=sub, sub_question=sq, defaults={'marks_obtained': marks}
            )
            sq_totals[sq.question_id] += marks

        # Roll sub-question totals up to question level
        for q_id, q_marks in sq_totals.items():
            q = get_object_or_404(Question, id=q_id)
            QuestionGrade.objects.update_or_create(
                submission=sub, question=q, defaults={'marks_obtained': q_marks}
            )
            total += q_marks

        # Plain question grades (questions without sub-questions)
        for qg_data in data.get('question_grades', []):
            q = get_object_or_404(Question, id=qg_data['question_id'])
            if q.id in sq_totals:
                continue  # already handled above
            marks = min(float(qg_data['marks']), q.max_marks)
            QuestionGrade.objects.update_or_create(
                submission=sub, question=q, defaults={'marks_obtained': marks}
            )
            total += marks
 
        was_graded_before = sub.status in ('graded', 'flagged')  # ← নতুন
 
        status = 'graded'
        sub.total_score = total
        sub.feedback    = data.get('feedback', '')
        sub.status      = status
        sub.save()

        recalculate_final_score(sub)

        if not was_graded_before:
            notify_grade_released(sub)
 
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_analytics(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None
    grade_dist = []
    clo_attainment = []
    student_details = []
    plo_attainment = []
    escar_clos = []
    escar_plos = []

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if selected_course:
        SUB_TYPES = {'mid', 'final'}

        # Only published assessments — same scope as marks sheet
        assessments = list(
            Assessment.objects.filter(course=selected_course, status='published')
            .prefetch_related(
                'questions__clos', 'questions__plos',
                'questions__sub_questions__clos', 'questions__sub_questions__plos',
            )
            .order_by('assessment_type', 'created_at')
        )

        # Build column list exactly like marks sheet:
        # mid/final → one column per sub-question (with sub-question CLOs/PLOs)
        # all others → one column per question (with question CLOs/PLOs)
        all_columns = []
        for a in assessments:
            use_subs = a.assessment_type in SUB_TYPES
            for q in a.questions.all().order_by('order'):
                subs = list(q.sub_questions.all().order_by('order')) if use_subs else []
                if use_subs and subs:
                    for sq in subs:
                        all_columns.append({
                            'is_sub':    True,
                            'entity_id': sq.id,
                            'max_marks': sq.max_marks,
                            'clo_ids':   [c.id for c in sq.clos.all()],
                            'plo_ids':   [p.id for p in sq.plos.all()],
                        })
                else:
                    all_columns.append({
                        'is_sub':    False,
                        'entity_id': q.id,
                        'max_marks': q.max_marks,
                        'clo_ids':   [c.id for c in q.clos.all()],
                        'plo_ids':   [p.id for p in q.plos.all()],
                    })

        clos = list(selected_course.clos.all())

        # Fixed denominators across ALL published assessments (same as marks sheet)
        clo_max = {
            clo.id: sum(col['max_marks'] for col in all_columns if clo.id in col['clo_ids'])
            for clo in clos
        }
        plo_ids_used = set()
        for col in all_columns:
            plo_ids_used.update(col['plo_ids'])
        plos = list(PLO.objects.filter(id__in=plo_ids_used))
        plo_map = {p.id: p for p in plos}
        plo_max = {
            p.id: sum(col['max_marks'] for col in all_columns if p.id in col['plo_ids'])
            for p in plos
        }
        total_max_overall = sum(col['max_marks'] for col in all_columns)

        # University grading scale buckets (label, lo_inclusive, hi_exclusive)
        GRADE_SCALE = [
            ('A+', 80, 200), ('A', 75, 80), ('A-', 70, 75),
            ('B+', 65, 70),  ('B', 60, 65), ('B-', 55, 60),
            ('C+', 50, 55),  ('C', 45, 50), ('D', 40, 45), ('F', 0, 40),
        ]
        grade_buckets = {label: 0 for label, _, _ in GRADE_SCALE}

        # Fetch all grades in two bulk queries (same as marks sheet)
        q_ids  = [col['entity_id'] for col in all_columns if not col['is_sub']]
        sq_ids = [col['entity_id'] for col in all_columns if col['is_sub']]
        q_grade_map  = {}
        sq_grade_map = {}
        if q_ids:
            for g in QuestionGrade.objects.filter(
                question_id__in=q_ids,
                submission__assessment__course=selected_course,
            ).select_related('submission__student'):
                q_grade_map.setdefault(g.submission.student_id, {})[g.question_id] = g.marks_obtained
        if sq_ids:
            for g in SubQuestionGrade.objects.filter(
                sub_question_id__in=sq_ids,
                submission__assessment__course=selected_course,
            ).select_related('submission__student'):
                sq_grade_map.setdefault(g.submission.student_id, {})[g.sub_question_id] = g.marks_obtained

        # All distinct enrolled students (no duplicate-enrollment risk)
        students = list(
            User.objects.filter(enrollments__course=selected_course)
            .distinct().order_by('full_name', 'username')
        )
        total_enrolled = len(students)

        clo_pct_sums = {clo.id: {'sum': 0.0, 'count': 0} for clo in clos}
        plo_pct_sums = {p.id: {'sum': 0.0, 'count': 0, 'plo': p} for p in plos}

        for student in students:
            sq_m = sq_grade_map.get(student.id, {})
            q_m  = q_grade_map.get(student.id, {})
            if not sq_m and not q_m:
                continue  # never graded — skip

            # Grade distribution — bucket this student's overall %
            if total_max_overall > 0:
                total_raw_student = sum(
                    sq_m.get(col['entity_id'], 0) if col['is_sub'] else q_m.get(col['entity_id'], 0)
                    for col in all_columns
                )
                student_pct = total_raw_student / total_max_overall * 100
                for lbl, lo, hi in GRADE_SCALE:
                    if lo <= student_pct < hi:
                        grade_buckets[lbl] += 1
                        break

            def _mark(col):
                return sq_m.get(col['entity_id'], 0) if col['is_sub'] else q_m.get(col['entity_id'], 0)

            clo_data = []
            for clo in clos:
                mx = clo_max[clo.id]
                if mx == 0:
                    continue
                raw = sum(_mark(col) for col in all_columns if clo.id in col['clo_ids'])
                pct = round(raw / mx * 100, 1)
                clo_data.append({'code': clo.code, 'pct': pct})
                clo_pct_sums[clo.id]['sum']   += pct
                clo_pct_sums[clo.id]['count'] += 1

            plo_data = []
            for p in plos:
                mx = plo_max[p.id]
                if mx == 0:
                    continue
                raw = sum(_mark(col) for col in all_columns if p.id in col['plo_ids'])
                pct = round(raw / mx * 100, 1)
                plo_data.append({'code': p.code, 'pct': pct})
                plo_pct_sums[p.id]['sum']   += pct
                plo_pct_sums[p.id]['count'] += 1

            overall_pcts = [d['pct'] for d in clo_data]
            overall = round(sum(overall_pcts) / len(overall_pcts), 1) if overall_pcts else 0.0
            student_details.append({
                'name':     student.full_name or student.username,
                'clo_data': clo_data,
                'plo_data': plo_data,
                'overall':  overall,
            })

        # Build grade_dist list for chart (preserve GRADE_SCALE order)
        grade_dist = [{'label': lbl, 'count': grade_buckets[lbl]} for lbl, _, _ in GRADE_SCALE]

        # Class-wide CLO attainment — average of per-student CLO %
        for clo in clos:
            d = clo_pct_sums[clo.id]
            avg = round(d['sum'] / d['count'], 1) if d['count'] > 0 else 0.0
            clo_attainment.append({'code': clo.code, 'attainment': avg})

        # Class-wide PLO attainment
        for p in plos:
            d = plo_pct_sums[p.id]
            avg = round(d['sum'] / d['count'], 1) if d['count'] > 0 else 0.0
            plo_attainment.append({'code': p.code, 'description': p.description, 'attainment': avg})

        # eSCAR — same averages, attained if class avg >= 60%
        for clo in clos:
            d = clo_pct_sums[clo.id]
            avg = round(d['sum'] / d['count'], 1) if d['count'] > 0 else 0.0
            attained = avg >= 60
            action = ('CLO attained. Maintain current teaching strategies.' if attained
                      else 'CLO not attained. Review teaching methods and provide additional practice.')
            escar_clos.append({'code': clo.code, 'count': d['count'], 'total': total_enrolled,
                               'pct': avg, 'attained': attained, 'action': action})

        for p in plos:
            d = plo_pct_sums[p.id]
            avg = round(d['sum'] / d['count'], 1) if d['count'] > 0 else 0.0
            attained = avg >= 60
            action = ('PLO attained. Continue current curriculum alignment.' if attained
                      else 'PLO not attained. Strengthen curriculum alignment and CLO coverage.')
            escar_plos.append({'code': p.code, 'count': d['count'], 'total': total_enrolled,
                               'pct': avg, 'attained': attained, 'action': action})

        escar_rows = [
            {'clo': escar_clos[i] if i < len(escar_clos) else None,
             'plo': escar_plos[i] if i < len(escar_plos) else None}
            for i in range(max(len(escar_clos), len(escar_plos), 1))
        ]
    else:
        escar_rows = []

    return render(request, 'faculty/analytics.html', {
        'courses': courses,
        'selected_course': selected_course,
        'grade_dist': json.dumps(grade_dist),
        'clo_attainment': json.dumps(clo_attainment),
        'clo_attainment_list': clo_attainment,
        'student_details': student_details,
        'plo_attainment': json.dumps(plo_attainment),
        'plo_attainment_list': plo_attainment,
        'escar_rows': escar_rows,
    })


@faculty_required
def faculty_escar(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None
    clos_data = []
    plos_data = []
    rows = []
    total_enrolled = 0
    total_participated = 0
    total_absent = 0

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if selected_course:
        assessments = Assessment.objects.filter(course=selected_course, status='published')
        enrolled_students = list(Enrollment.objects.filter(course=selected_course).select_related('student'))
        total_enrolled = len(enrolled_students)

        # Read all grades the same way the marksheet does — no submission-status filter.
        all_q_ids = list(Question.objects.filter(assessment__in=assessments).values_list('id', flat=True))
        all_grades = QuestionGrade.objects.filter(
            question_id__in=all_q_ids,
            submission__assessment__course=selected_course,
        ).values('submission__student_id', 'question_id', 'marks_obtained')

        # grade_map mirrors the marksheet: {student_id: {question_id: marks}}
        grade_map = {}
        for g in all_grades:
            sid = g['submission__student_id']
            grade_map.setdefault(sid, {})[g['question_id']] = g['marks_obtained']

        participated_ids = set(grade_map.keys())
        total_participated = len(participated_ids)
        total_absent = total_enrolled - total_participated

        # Build question max-marks cache once for all questions in the course
        q_maxmarks = {q.id: q.max_marks for q in Question.objects.filter(id__in=all_q_ids)}

        def _attainment(q_ids, q_marks_map):
            """Return (students_passed, students_assessed, attainment_pct) for a set of question IDs."""
            s_passed = 0
            s_assessed = 0
            for enrollment in enrolled_students:
                sid = enrollment.student_id
                if sid not in participated_ids:
                    continue
                sg = grade_map.get(sid, {})
                # Only questions this student actually has a grade for
                student_q_grades = {qid: sg[qid] for qid in q_ids if qid in sg}
                if not student_q_grades:
                    continue
                student_max = sum(q_marks_map.get(qid, 0) for qid in student_q_grades)
                if student_max == 0:
                    continue
                obtained = sum(student_q_grades.values())
                s_assessed += 1
                if (obtained / student_max * 100) >= 40:
                    s_passed += 1
            pct = round((s_passed / s_assessed * 100) if s_assessed > 0 else 0, 2)
            return s_passed, s_assessed, pct

        for clo in selected_course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            q_marks_map = {qid: q_maxmarks[qid] for qid in q_ids if qid in q_maxmarks}
            s_passed, s_assessed, attainment_pct = _attainment(q_ids, q_marks_map) if q_ids else (0, 0, 0.0)
            plan_obj = CLOActionPlan.objects.filter(course=selected_course, clo=clo).first()
            clos_data.append({
                'id': clo.id,
                'code': clo.code,
                'description': clo.description,
                'students_assessed': s_assessed,
                'students_passed': s_passed,
                'attainment_pct': attainment_pct,
                'attained': attainment_pct >= 60,
                'action_plan': plan_obj.action_plan if plan_obj else '',
            })

        # PLO mapping via CLO.plos (PLOs are assigned to CLOs, not questions directly)
        plo_q_map = defaultdict(set)
        plo_obj_map = {}
        for clo in selected_course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            for plo in clo.plos.all():
                plo_q_map[plo.id].update(q_ids)
                plo_obj_map[plo.id] = plo

        for plo_id, q_id_set in plo_q_map.items():
            plo = plo_obj_map[plo_id]
            q_ids = list(q_id_set)
            if not q_ids:
                continue
            q_marks_map = {qid: q_maxmarks[qid] for qid in q_ids if qid in q_maxmarks}
            s_passed, s_assessed, attainment_pct = _attainment(q_ids, q_marks_map)
            plan_obj = PLOActionPlan.objects.filter(course=selected_course, plo=plo).first()
            plos_data.append({
                'id': plo.id,
                'code': plo.code,
                'description': plo.description,
                'students_assessed': s_assessed,
                'students_passed': s_passed,
                'attainment_pct': attainment_pct,
                'attained': attainment_pct >= 60,
                'action_plan': plan_obj.action_plan if plan_obj else '',
            })

        max_len = max(len(clos_data), len(plos_data), 1)
        for i in range(max_len):
            rows.append({
                'clo': clos_data[i] if i < len(clos_data) else None,
                'plo': plos_data[i] if i < len(plos_data) else None,
            })

    return render(request, 'faculty/escar.html', {
        'courses': courses,
        'selected_course': selected_course,
        'rows': rows,
        'total_enrolled': total_enrolled,
        'total_participated': total_participated,
        'total_absent': total_absent,
    })


@faculty_required
def save_escar_plan(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    data = json.loads(request.body)
    course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
    plan_type = data.get('type')
    plan_text = data.get('action_plan', '')
    if plan_type == 'clo':
        clo = get_object_or_404(CLO, id=data['id'], course=course)
        obj, _ = CLOActionPlan.objects.get_or_create(course=course, clo=clo)
        obj.action_plan = plan_text
        obj.save()
    elif plan_type == 'plo':
        plo = get_object_or_404(PLO, id=data['id'])
        obj, _ = PLOActionPlan.objects.get_or_create(course=course, plo=plo)
        obj.action_plan = plan_text
        obj.save()
    else:
        return JsonResponse({'error': 'Invalid type'}, status=400)
    return JsonResponse({'success': True})


@faculty_required
def faculty_announcements(request):
    courses = Course.objects.filter(faculty=request.user)
    announcements = Announcement.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-created_at')
    return render(request, 'faculty/announcements.html', {
        'announcements': announcements, 'courses': courses
    })


@faculty_required
def create_announcement(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        ann = Announcement.objects.create(
            course=course, title=data['title'], content=data['content'],
            priority=data.get('priority', 'medium'), created_by=request.user
        )
        notify_announcement(ann) 
        return JsonResponse({'success': True, 'id': ann.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_announcement(request, ann_id):
    ann = get_object_or_404(Announcement, id=ann_id, created_by=request.user)
    ann.delete()
    return JsonResponse({'success': True})


# Student Views

@student_required
def student_dashboard(request):
    now = timezone.now()
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course', 'course__faculty')
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(course__in=courses, status='published')
    submissions = Submission.objects.filter(student=request.user, assessment__in=assessments)
    submitted_ids = submissions.values_list('assessment_id', flat=True)

    pending_qs = assessments.exclude(id__in=submitted_ids).select_related('course').order_by('due_date')
    pending_count = pending_qs.count()
    upcoming = pending_qs.filter(due_date__isnull=False, due_date__gte=now)[:5]

    graded = submissions.filter(status='graded').select_related('assessment', 'assessment__course')
    avg_grade = 0
    if graded.exists():
        total_pct = sum(
            s.total_score / s.assessment.total_marks * 100
            for s in graded if s.assessment.total_marks > 0
        )
        avg_grade = round(total_pct / graded.count(), 1)

    recent_grades = graded.order_by('-submitted_at')[:5]
    announcements = Announcement.objects.filter(course__in=courses).order_by('-created_at')[:4]

    return render(request, 'student/dashboard.html', {
        'courses': courses,
        'submissions_count': submissions.count(),
        'pending_count': pending_count,
        'graded_count': graded.count(),
        'avg_grade': avg_grade,
        'recent_grades': recent_grades,
        'announcements': announcements,
        'upcoming': upcoming,
    })


@student_required
def student_courses(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    courses = []
    for e in enrollments:
        c = e.course
        c.clos_list = c.clos.prefetch_related('plos').all()
        c.assignment_count = Assessment.objects.filter(course=c, status='published').count()
        courses.append(c)
    return render(request, 'student/courses.html', {'courses': courses})


@student_required
def enroll_via_code(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
        try:
            course = Course.objects.get(enrollment_code=code)
            _, created = Enrollment.objects.get_or_create(student=request.user, course=course)
            if created:
                return JsonResponse({'success': True, 'course': f"{course.code}: {course.name}"})
            return JsonResponse({'error': 'You are already enrolled in this course.'}, status=400)
        except Course.DoesNotExist:
            return JsonResponse({'error': 'Invalid enrollment code. Please check and try again.'}, status=404)
    return JsonResponse({'error': 'POST required'}, status=400)


@student_required
def unenroll_course(request, course_id):
    if request.method == 'POST':
        enrollment = get_object_or_404(Enrollment, student=request.user, course_id=course_id)
        enrollment.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@student_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(student=request.user, course=course)
    return JsonResponse({'success': True})


@student_required
def student_submissions(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(course__in=courses, status='published')
    submissions = Submission.objects.filter(
        student=request.user, assessment__in=assessments
    ).select_related('assessment__course').order_by('-submitted_at')
    submitted_ids = submissions.values_list('assessment_id', flat=True)
    pending = assessments.exclude(id__in=submitted_ids)
    today = date.today()
    todo_assessments = pending.filter(due_date__gte=today) | pending.filter(due_date__isnull=True)
    missing_assessments = pending.filter(due_date__lt=today)
    return render(request, 'student/submissions.html', {
        'submissions': submissions,
        'todo_assessments': todo_assessments,
        'missing_assessments': missing_assessments,
        'pending_assessments': todo_assessments | missing_assessments,
    })


@student_required
def submit_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id, status='published')
    if not Enrollment.objects.filter(student=request.user, course=assessment.course).exists():
        return JsonResponse({'error': 'Not enrolled'}, status=403)
    if request.method == 'POST':
        data = json.loads(request.body)
        content = data.get('content', '')
        sub, created = Submission.objects.get_or_create(
            student=request.user, assessment=assessment,
            defaults={
                'content': content,
                'plagiarism_score': round(len(content) % 50, 1),
                'ai_content_score': round(len(content) % 20, 1),
            }
        )
        if not created:
            return JsonResponse({'error': 'Already submitted'}, status=400)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@student_required
def student_clo_results(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    results = []
    for e in enrollments:
        course = e.course
        assessments = Assessment.objects.filter(course=course, status='published')
        subs = Submission.objects.filter(
            student=request.user, assessment__in=assessments,
            status__in=['graded', 'flagged']
        )
        avg_pct = 0
        if subs.exists():
            total = sum(
                (s.total_score / s.assessment.total_marks * 100)
                for s in subs if s.assessment.total_marks > 0
            )
            avg_pct = round(total / subs.count(), 1)
        grade = 'F'
        if avg_pct >= 80: grade = 'A+'
        elif avg_pct >= 75: grade = 'A'
        elif avg_pct >= 70: grade = 'A-'
        elif avg_pct >= 65: grade = 'B+'
        elif avg_pct >= 60: grade = 'B'
        elif avg_pct >= 55: grade = 'B-'
        elif avg_pct >= 50: grade = 'C+'
        elif avg_pct >= 45: grade = 'C'
        elif avg_pct >= 40: grade = 'D'

        clo_results = []
        plo_agg = defaultdict(lambda: {'obtained': 0.0, 'total': 0.0, 'plo': None})
        for clo in course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=subs)
            total_possible = sum(Question.objects.get(id=qid).max_marks for qid in q_ids)
            total_obtained = sum(g.marks_obtained for g in qgs)
            attainment = round((total_obtained / total_possible * 100) if total_possible > 0 else 0, 1)
            clo_results.append({
                'code': clo.code, 'bloom': clo.bloom_level,
                'description': clo.description,
                'obtained': int(total_obtained), 'total': int(total_possible),
                'attainment': attainment
            })
            for plo in clo.plos.all():
                if plo_agg[plo.id]['plo'] is None:
                    plo_agg[plo.id]['plo'] = plo
                plo_agg[plo.id]['obtained'] += total_obtained
                plo_agg[plo.id]['total'] += total_possible

        plo_results = []
        for pid, data in plo_agg.items():
            plo = data['plo']
            att = round((data['obtained'] / data['total'] * 100) if data['total'] > 0 else 0, 1)
            plo_results.append({'code': plo.code, 'description': plo.description, 'attainment': att})

        results.append({
            'course': course, 'grade': grade,
            'avg_pct': avg_pct, 'graded_count': subs.count(),
            'clo_results': clo_results,
            'plo_results': plo_results,
        })
    return render(request, 'student/clo_results.html', {'results': results})


@student_required
def student_notifications(request):
    notifs      = Notification.objects.filter(
        recipient=request.user
    ).select_related('course', 'assessment')
    unread_count = notifs.filter(is_read=False).count()
    # mark all read when page opens
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'student/notifications.html', {
        'notifs':       notifs,
        'unread_count': unread_count,
    })



# Study Material Views 

@faculty_required
def faculty_materials(request):
    courses = Course.objects.filter(faculty=request.user)
 
    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
        materials = StudyMaterial.objects.filter(
            course=selected_course
        ).order_by('-uploaded_at')
        return render(request, 'faculty/materials.html', {
            'selected_course': selected_course,
            'courses': courses,
            'materials': materials,
            'material_count': materials.count(),
        })
 
    # Course list view — annotate counts
    for c in courses:
        c.material_count = StudyMaterial.objects.filter(course=c).count()
        c.visible_count  = StudyMaterial.objects.filter(course=c, is_visible=True).count()
        c.hidden_count   = StudyMaterial.objects.filter(course=c, is_visible=False).count()
 
    return render(request, 'faculty/materials.html', {
        'selected_course': None,
        'courses': courses,
    })


@faculty_required
def upload_material(request):
    if request.method == 'POST':
        course_id     = request.POST.get('course_id')
        title         = request.POST.get('title', '').strip()
        description   = request.POST.get('description', '').strip()
        material_type = request.POST.get('material_type', 'lecture_note')
        video_url     = request.POST.get('video_url', '').strip()
        uploaded_file = request.FILES.get('file')
 
        course = get_object_or_404(Course, id=course_id, faculty=request.user)
 
        # ── Permission check ──
        if not title:
            return JsonResponse({'error': 'Title is required.'}, status=400)
        if material_type == 'video' and not video_url and not uploaded_file:
            return JsonResponse({'error': 'Please provide a video URL or upload a video file.'}, status=400)
        if material_type != 'video' and not uploaded_file and not video_url:
            return JsonResponse({'error': 'Please select a file to upload.'}, status=400)
 
        material = StudyMaterial.objects.create(
            course=course,
            title=title,
            description=description,
            material_type=material_type,
            file=uploaded_file,
            video_url=video_url,
            uploaded_by=request.user,
            is_visible=True,
        )
        return JsonResponse({
            'success':       True,
            'id':            material.id,
            'title':         material.title,
            'description':   material.description,
            'material_type': material.material_type,
            'type_label':    material.get_material_type_display(),
            'file_url':      material.file.url if material.file else '',
            'filename':      material.filename(),
            'video_url':     material.video_url,
            'embed_url':     material.embed_url(),
            'is_video':      material.is_video(),
            'is_visible':    material.is_visible,
            'uploaded_at':   material.uploaded_at.strftime('%b %d, %Y'),
        })
    return JsonResponse({'error': 'POST required'}, status=400)

@faculty_required
def toggle_material_visibility(request, material_id):
    """Faculty can show/hide a material from students."""
    material = get_object_or_404(StudyMaterial, id=material_id, course__faculty=request.user)
    material.is_visible = not material.is_visible
    material.save()
    return JsonResponse({'success': True, 'is_visible': material.is_visible})


@faculty_required
def delete_material(request, material_id):
    material = get_object_or_404(StudyMaterial, id=material_id, course__faculty=request.user)
    if material.file:
        material.file.delete(save=False)
    material.delete()
    return JsonResponse({'success': True})


@student_required
def student_materials(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses     = [e.course for e in enrollments]
 
    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=int(course_id))
 
        # Permission check — must be enrolled
        if selected_course not in courses:
            from django.shortcuts import redirect
            return redirect('student_materials')
 
        # Only show visible materials
        materials = StudyMaterial.objects.filter(
            course=selected_course,
            is_visible=True,         # ← students only see visible ones
        ).order_by('-uploaded_at')
 
        return render(request, 'student/materials.html', {
            'selected_course': selected_course,
            'materials':       materials,
            'material_count':  materials.count(),
        })
 
    # Course list
    for c in courses:
        c.material_count = StudyMaterial.objects.filter(course=c, is_visible=True).count()
 
    return render(request, 'student/materials.html', {
        'selected_course': None,
        'courses':         courses,
    })

@faculty_required
def add_plo(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        desc = data.get('description', '').strip()
        if not desc:
            return JsonResponse({'error': 'Description required'}, status=400)
        count = PLO.objects.count() + 1
        plo = PLO.objects.create(
            code=f"PLO{count}",
            description=desc,
            created_by=request.user
        )
        return JsonResponse({'success': True, 'id': plo.id, 'code': plo.code})
    return JsonResponse({'error': 'POST required'}, status=400)


# Faculty Assignment Views 

@faculty_required
def faculty_assignments(request):
    courses = Course.objects.filter(faculty=request.user)
    plos = PLO.objects.all()

    course_id = request.GET.get('course')
    if course_id:
        # Course detail view 
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
        base_qs = Assessment.objects.filter(course=selected_course).select_related('course').prefetch_related(
            'questions', 'questions__clos', 'questions__plos'
        )
        drafts = list(base_qs.filter(status='draft').order_by('-created_at'))
        published_list = list(base_qs.filter(status='published').order_by('-created_at'))
        for a in drafts + published_list:
            a.submission_count = a.submissions.count()
            a.question_count = a.questions.count()
        return render(request, 'faculty/assignments.html', {
            'selected_course': selected_course,
            'courses': courses,
            'drafts': drafts,
            'published_list': published_list,
            'plos': plos,
            'draft_count': len(drafts),
            'published_count': len(published_list),
            'total_subs': sum(a.submission_count for a in published_list),
        })

    # Course list view 
    for c in courses:
        c.total_count = Assessment.objects.filter(course=c).count()
        c.draft_count = Assessment.objects.filter(course=c, status='draft').count()
        c.published_count = Assessment.objects.filter(course=c, status='published').count()
    return render(request, 'faculty/assignments.html', {
        'selected_course': None,
        'courses': courses,
        'plos': plos,
    })


def _decode_image(b64_str, prefix='img'):
    """Decode a base64 data-URL string into a ContentFile. Returns None on failure."""
    if not b64_str or ',' not in b64_str:
        return None
    try:
        header, data = b64_str.split(',', 1)
        ext = header.split('/')[1].split(';')[0]
        return ContentFile(base64.b64decode(data), name=f'{prefix}_{uuid.uuid4().hex[:8]}.{ext}')
    except Exception:
        return None


@faculty_required
def create_assignment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        assessment_type = data.get('assessment_type', 'assignment')
        # Faculty can explicitly choose publish or draft; assignment defaults to publish
        default_publish = assessment_type == 'assignment'
        publish_immediately = data.get('publish_immediately', default_publish)
        status = 'published' if publish_immediately else 'draft'
        # due_date is optional for non-assignment types
        due_date = data.get('due_date') or None
        assignment = Assessment.objects.create(
            course=course,
            title=data['title'],
            description=data.get('description', ''),
            assessment_type=assessment_type,
            due_date=due_date,
            status=status,
            total_marks=0,
            grace_period_hours   = int(data.get('grace_period_hours', 0)),
            late_deduction_type  = data.get('late_deduction_type', 'percent'),
            late_deduction_value = float(data.get('late_deduction_value', 0)),
            max_late_days        = int(data.get('max_late_days', 0)),
        )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            question = Question.objects.create(
                assessment=assignment,
                order=i,
                text=q['text'],
                max_marks=0,
            )
            # Question-level image
            img_file = _decode_image(q.get('image_b64'), f'q{i}')
            if img_file:
                question.image.save(img_file.name, img_file, save=False)

            sub_questions = q.get('sub_questions', [])
            if sub_questions:
                all_clo_ids, all_plo_ids, q_total = set(), set(), 0
                for j, sq in enumerate(sub_questions, 1):
                    sub = SubQuestion.objects.create(
                        question=question,
                        order=j,
                        text=sq['text'],
                        max_marks=int(sq.get('max_marks', 5)),
                    )
                    sq_img = _decode_image(sq.get('image_b64'), f'sq{i}_{j}')
                    if sq_img:
                        sub.image.save(sq_img.name, sq_img, save=False)
                    if sq.get('clo_ids'):
                        sub.clos.set(CLO.objects.filter(id__in=sq['clo_ids']))
                        all_clo_ids.update(sq['clo_ids'])
                    if sq.get('plo_ids'):
                        sub.plos.set(PLO.objects.filter(id__in=sq['plo_ids']))
                        all_plo_ids.update(sq['plo_ids'])
                    sub.save()
                    q_total += int(sq.get('max_marks', 5))
                question.max_marks = q_total
                if all_clo_ids:
                    question.clos.set(CLO.objects.filter(id__in=all_clo_ids))
                if all_plo_ids:
                    question.plos.set(PLO.objects.filter(id__in=all_plo_ids))
                total += q_total
            else:
                # Fallback: question-level marks/CLO/PLO (backward compat)
                question.max_marks = int(q.get('max_marks', 10))
                if q.get('clo_ids'):
                    question.clos.set(CLO.objects.filter(id__in=q['clo_ids']))
                if q.get('plo_ids'):
                    question.plos.set(PLO.objects.filter(id__in=q['plo_ids']))
                total += question.max_marks
            question.save()
        # Use manual total_marks if provided and no questions, else sum of questions
        manual_total = int(data.get('total_marks', 0))
        assignment.total_marks = total if total > 0 else manual_total
        assignment.save()

        if status == 'published':
            notify_new_assignment(assignment)

        type_labels = dict(Assessment.TYPE_CHOICES)
        return JsonResponse({
            'success': True,
            'id': assignment.id,
            'title': assignment.title,
            'type_label': type_labels.get(assessment_type, assessment_type),
            'assessment_type': assessment_type,
            'status': status,
            'course_name': f"{course.code}: {course.name}",
            'due_date': str(assignment.due_date),
            'total_marks': assignment.total_marks,
            'description': assignment.description,
            'question_count': len(data.get('questions', [])),
        })
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(
        Assessment, id=assignment_id, course__faculty=request.user
    )
    assignment.delete()
    return JsonResponse({'success': True})


@faculty_required
def get_assessment_data(request, assignment_id):
    assessment = get_object_or_404(Assessment, id=assignment_id, course__faculty=request.user)
    questions = []
    for q in assessment.questions.order_by('order'):
        subs = []
        for sq in q.sub_questions.order_by('order'):
            subs.append({
                'id': sq.id,
                'text': sq.text,
                'max_marks': sq.max_marks,
                'image_url':  request.build_absolute_uri(sq.image.url) if sq.image else None,
                'image_name': sq.image.name if sq.image else None,
                'clo_ids': list(sq.clos.values_list('id', flat=True)),
                'plo_ids': list(sq.plos.values_list('id', flat=True)),
            })
        questions.append({
            'id': q.id,
            'text': q.text,
            'max_marks': q.max_marks,
            'image_url':  request.build_absolute_uri(q.image.url) if q.image else None,
            'image_name': q.image.name if q.image else None,
            'clo_ids': list(q.clos.values_list('id', flat=True)),
            'plo_ids': list(q.plos.values_list('id', flat=True)),
            'sub_questions': subs,
        })
    return JsonResponse({
        'id': assessment.id,
        'title': assessment.title,
        'description': assessment.description,
        'assessment_type': assessment.assessment_type,
        'due_date': str(assessment.due_date) if assessment.due_date else '',
        'status': assessment.status,
        'grace_period_hours':   assessment.grace_period_hours,
        'max_late_days':        assessment.max_late_days,
        'late_deduction_type':  assessment.late_deduction_type,
        'late_deduction_value': assessment.late_deduction_value,
        'questions': questions,
    })


@faculty_required
def edit_assessment(request, assignment_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    assessment = get_object_or_404(Assessment, id=assignment_id, course__faculty=request.user)
    data = json.loads(request.body)
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required.'}, status=400)

    assessment.title                = title
    assessment.description          = data.get('description', '').strip()
    assessment.due_date             = data.get('due_date') or None
    assessment.grace_period_hours   = int(data.get('grace_period_hours', 0) or 0)
    assessment.max_late_days        = int(data.get('max_late_days', 0) or 0)
    assessment.late_deduction_type  = data.get('late_deduction_type', 'percent')
    assessment.late_deduction_value = float(data.get('late_deduction_value', 0) or 0)
    assessment.save()

    # Rebuild all questions from submitted data
    assessment.questions.all().delete()
    total = 0
    for i, q in enumerate(data.get('questions', []), 1):
        question = Question.objects.create(
            assessment=assessment, order=i, text=q['text'], max_marks=0,
        )
        img_file = _decode_image(q.get('image_b64'), f'q{i}')
        if img_file:
            question.image.save(img_file.name, img_file, save=False)
        elif q.get('existing_image_name'):
            question.image.name = q['existing_image_name']

        sub_questions = q.get('sub_questions', [])
        if sub_questions:
            all_clo_ids, all_plo_ids, q_total = set(), set(), 0
            for j, sq in enumerate(sub_questions, 1):
                sub = SubQuestion.objects.create(
                    question=question, order=j,
                    text=sq['text'], max_marks=int(sq.get('max_marks', 5)),
                )
                sq_img = _decode_image(sq.get('image_b64'), f'sq{i}_{j}')
                if sq_img:
                    sub.image.save(sq_img.name, sq_img, save=False)
                elif sq.get('existing_image_name'):
                    sub.image.name = sq['existing_image_name']
                if sq.get('clo_ids'):
                    sub.clos.set(CLO.objects.filter(id__in=sq['clo_ids']))
                    all_clo_ids.update(sq['clo_ids'])
                if sq.get('plo_ids'):
                    sub.plos.set(PLO.objects.filter(id__in=sq['plo_ids']))
                    all_plo_ids.update(sq['plo_ids'])
                sub.save()
                q_total += int(sq.get('max_marks', 5))
            question.max_marks = q_total
            if all_clo_ids:
                question.clos.set(CLO.objects.filter(id__in=all_clo_ids))
            if all_plo_ids:
                question.plos.set(PLO.objects.filter(id__in=all_plo_ids))
            total += q_total
        else:
            question.max_marks = int(q.get('max_marks', 0))
            if q.get('clo_ids'):
                question.clos.set(CLO.objects.filter(id__in=q['clo_ids']))
            if q.get('plo_ids'):
                question.plos.set(PLO.objects.filter(id__in=q['plo_ids']))
            total += question.max_marks
        question.save()

    manual_total = int(data.get('total_marks', 0))
    assessment.total_marks = total if total > 0 else manual_total
    assessment.save()
    return JsonResponse({'success': True})


@faculty_required
def publish_assessment(request, assignment_id):
    assessment = get_object_or_404(
        Assessment, id=assignment_id, course__faculty=request.user
    )
    assessment.status = 'published'
    assessment.save()
    notify_new_assignment(assessment)
 
    return JsonResponse({'success': True})


# Student Assignment Views 

@student_required
def student_assignments(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    course_cards = []
    for e in enrollments:
        course = e.course
        total = Assessment.objects.filter(course=course, status='published').count()
        submitted = Submission.objects.filter(
            student=request.user, assessment__course=course
        ).count()
        if total > 0:
            course_cards.append({
                'course':    course,
                'total':     total,
                'submitted': submitted,
                'pending':   total - submitted,
            })
    return render(request, 'student/assignments.html', {'course_cards': course_cards})


@student_required
def student_course_assignments(request, course_id):
    enrolled_ids = list(Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True))
    if course_id not in enrolled_ids:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    course = get_object_or_404(Course, id=course_id)
    assessments = Assessment.objects.filter(
        course=course, status='published'
    ).prefetch_related('questions__clos', 'questions__plos').order_by('-created_at')
    submissions = {
        s.assessment_id: s
        for s in Submission.objects.filter(student=request.user, assessment__in=assessments)
    }
    assignments_with_status = []
    for a in assessments:
        sub    = submissions.get(a.id)
        window = check_submission_window(a) if not sub else None
        assignments_with_status.append((a, sub, window))
    return render(request, 'student/course_assignments.html', {
        'course':                  course,
        'assignments_with_status': assignments_with_status,
    })


@student_required
def submit_assignment(request, assignment_id):
    from django.shortcuts import redirect as _redirect
    assignment = get_object_or_404(Assessment, id=assignment_id, status='published')

    if not Enrollment.objects.filter(student=request.user, course=assignment.course).exists():
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    existing_sub = Submission.objects.filter(student=request.user, assessment=assignment).first()
    window       = check_submission_window(assignment)
    questions    = assignment.questions.prefetch_related(
        'clos', 'plos',
        'sub_questions__clos', 'sub_questions__plos',
    ).order_by('order')

    error = None

    if request.method == 'POST':
        if existing_sub:
            error = 'You have already submitted this assignment.'
        elif not window['can_submit']:
            error = window['window_msg']
        else:
            content       = request.POST.get('content', '').strip()
            uploaded_file = request.FILES.get('submitted_file')
            if not content and not uploaded_file:
                error = 'Please provide an answer or upload a file.'
            else:
                sub = Submission.objects.create(
                    student=request.user,
                    assessment=assignment,
                    content=content,
                    submitted_file=uploaded_file,
                )
                apply_late_deduction(sub)
                return _redirect('student_assignments')

    return render(request, 'student/submit_assignment.html', {
        'assignment':   assignment,
        'questions':    questions,
        'existing_sub': existing_sub,
        'window':       window,
        'error':        error,
    })


@student_required
def unsubmit_assignment(request, assignment_id):
    from django.shortcuts import redirect as _redirect
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    assignment = get_object_or_404(Assessment, id=assignment_id, status='published')
    sub = Submission.objects.filter(student=request.user, assessment=assignment).first()

    if not sub:
        return JsonResponse({'error': 'No submission found.'}, status=404)
    if sub.status == 'graded':
        return JsonResponse({'error': 'Cannot unsubmit a graded submission.'}, status=403)

    sub.delete()
    return _redirect('submit_assignment', assignment_id=assignment_id)


@faculty_required
def faculty_marks_sheet(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if not selected_course:
        return render(request, 'faculty/marks_sheet.html', {'courses': courses, 'selected_course': None})

    SUB_TYPES = {'mid', 'final'}
    ALPHA = 'abcdefghijklmnopqrstuvwxyz'

    assessments = list(
        Assessment.objects.filter(course=selected_course, status='published')
        .prefetch_related(
            'questions__clos', 'questions__plos',
            'questions__sub_questions__clos', 'questions__sub_questions__plos',
        )
        .order_by('assessment_type', 'created_at')
    )

    all_columns = []
    assessment_groups = []
    for a in assessments:
        questions = list(a.questions.all().order_by('order'))
        if not questions:
            continue
        use_subs = a.assessment_type in SUB_TYPES
        cols_for_a = []
        for q in questions:
            subs = list(q.sub_questions.all().order_by('order')) if use_subs else []
            if use_subs and subs:
                for idx, sq in enumerate(subs):
                    col = {
                        'label':     f"Q{q.order} ({ALPHA[idx]})",
                        'is_sub':    True,
                        'col_id':    f"sq_{sq.id}",
                        'col_type':  'sub',
                        'entity_id': sq.id,
                        'question':  q,
                        'sub_q':     sq,
                        'max_marks': sq.max_marks,
                        'clo_ids':   [c.id for c in sq.clos.all()],
                        'plo_ids':   [p.id for p in sq.plos.all()],
                        'clo_codes': [c.code for c in sq.clos.all()],
                        'plo_codes': [p.code for p in sq.plos.all()],
                    }
                    cols_for_a.append(col)
                    all_columns.append(col)
            else:
                col = {
                    'label':     f"Q{q.order}",
                    'is_sub':    False,
                    'col_id':    f"q_{q.id}",
                    'col_type':  'q',
                    'entity_id': q.id,
                    'question':  q,
                    'sub_q':     None,
                    'max_marks': q.max_marks,
                    'clo_ids':   [c.id for c in q.clos.all()],
                    'plo_ids':   [p.id for p in q.plos.all()],
                    'clo_codes': [c.code for c in q.clos.all()],
                    'plo_codes': [p.code for p in q.plos.all()],
                }
                cols_for_a.append(col)
                all_columns.append(col)
        assessment_groups.append({'assessment': a, 'questions': questions, 'col_count': len(cols_for_a)})

    students = list(
        User.objects.filter(enrollments__course=selected_course)
        .distinct().order_by('full_name', 'username')
    )

    # Fetch question-level grades (non-sub columns)
    q_ids = [col['entity_id'] for col in all_columns if not col['is_sub']]
    q_grade_map = {}
    if q_ids:
        for g in QuestionGrade.objects.filter(
            question_id__in=q_ids,
            submission__assessment__course=selected_course
        ).select_related('submission__student'):
            q_grade_map.setdefault(g.submission.student_id, {})[g.question_id] = g.marks_obtained

    # Fetch sub-question-level grades (mid/final sub columns)
    sq_ids = [col['entity_id'] for col in all_columns if col['is_sub']]
    sq_grade_map = {}
    if sq_ids:
        for g in SubQuestionGrade.objects.filter(
            sub_question_id__in=sq_ids,
            submission__assessment__course=selected_course
        ).select_related('submission__student'):
            sq_grade_map.setdefault(g.submission.student_id, {})[g.sub_question_id] = g.marks_obtained

    clos = list(selected_course.clos.all().order_by('code'))
    plo_ids_used = set()
    for col in all_columns:
        plo_ids_used.update(col['plo_ids'])
    plos = list(PLO.objects.filter(id__in=plo_ids_used).order_by('code'))

    clo_max = {
        clo.id: sum(col['max_marks'] for col in all_columns if clo.id in col['clo_ids'])
        for clo in clos
    }
    plo_max = {
        plo.id: sum(col['max_marks'] for col in all_columns if plo.id in col['plo_ids'])
        for plo in plos
    }
    total_max = sum(col['max_marks'] for col in all_columns)

    rows = []
    for i, student in enumerate(students):
        sq_m = sq_grade_map.get(student.id, {})
        q_m  = q_grade_map.get(student.id, {})

        def _val(col):
            return sq_m.get(col['entity_id']) if col['is_sub'] else q_m.get(col['entity_id'])

        cells = [
            {
                'col_id':    col['col_id'],
                'col_type':  col['col_type'],
                'entity_id': col['entity_id'],
                'max_marks': col['max_marks'],
                'value':     _val(col),
            }
            for col in all_columns
        ]
        total = sum(c['value'] for c in cells if c['value'] is not None)

        clo_cells = [
            {'clo_id': clo.id, 'code': clo.code, 'max': clo_max[clo.id],
             'raw': sum(
                 (sq_m.get(col['entity_id'], 0) if col['is_sub'] else q_m.get(col['entity_id'], 0))
                 for col in all_columns if clo.id in col['clo_ids']
             )}
            for clo in clos
        ]
        plo_cells = [
            {'plo_id': plo.id, 'code': plo.code, 'max': plo_max[plo.id],
             'raw': sum(
                 (sq_m.get(col['entity_id'], 0) if col['is_sub'] else q_m.get(col['entity_id'], 0))
                 for col in all_columns if plo.id in col['plo_ids']
             )}
            for plo in plos
        ]
        rows.append({
            'sl': i + 1,
            'student': student,
            'cells':   cells,
            'total':   total,
            'clo_cells': clo_cells,
            'plo_cells': plo_cells,
        })

    clo_max_list = [{'clo': c, 'max': clo_max[c.id]} for c in clos]
    plo_max_list = [{'plo': p, 'max': plo_max[p.id]} for p in plos]
    t2_colspan = 2 + 3 * (len(clos) + len(plos))

    js_columns = json.dumps([
        {
            'col_id':    col['col_id'],
            'col_type':  col['col_type'],
            'entity_id': col['entity_id'],
            'max':       col['max_marks'],
            'clo_ids':   col['clo_ids'],
            'plo_ids':   col['plo_ids'],
        }
        for col in all_columns
    ])
    js_clos = json.dumps([{'id': c.id, 'code': c.code, 'max': clo_max[c.id]} for c in clos])
    js_plos = json.dumps([{'id': p.id, 'code': p.code, 'max': plo_max[p.id]} for p in plos])

    return render(request, 'faculty/marks_sheet.html', {
        'courses':           courses,
        'selected_course':   selected_course,
        'assessment_groups': assessment_groups,
        'all_columns':       all_columns,
        'rows':              rows,
        'clos':              clos,
        'plos':              plos,
        'clo_max':           clo_max,
        'plo_max':           plo_max,
        'total_max':         total_max,
        'clo_max_list':      clo_max_list,
        'plo_max_list':      plo_max_list,
        't2_colspan':        t2_colspan,
        'js_columns':        js_columns,
        'js_clos':           js_clos,
        'js_plos':           js_plos,
    })


@faculty_required
def update_question_grade(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    data = json.loads(request.body)
    try:
        marks = float(data.get('marks', 0))
    except (TypeError, ValueError):
        marks = 0

    student = get_object_or_404(User, id=data.get('student_id'))
    col_type = data.get('col_type', 'q')

    if col_type == 'sub':
        sub_q = get_object_or_404(SubQuestion, id=data.get('entity_id'))
        if sub_q.question.assessment.course.faculty != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        marks = min(max(marks, 0), sub_q.max_marks)
        submission, _ = Submission.objects.get_or_create(
            student=student, assessment=sub_q.question.assessment,
            defaults={'content': '', 'status': 'graded', 'total_score': 0,
                      'plagiarism_score': 0, 'ai_content_score': 0}
        )
        SubQuestionGrade.objects.update_or_create(
            submission=submission, sub_question=sub_q,
            defaults={'marks_obtained': marks}
        )
        # Roll up sub-question totals to QuestionGrade
        sq_total = sum(
            g.marks_obtained
            for g in SubQuestionGrade.objects.filter(
                submission=submission, sub_question__question=sub_q.question
            )
        )
        QuestionGrade.objects.update_or_create(
            submission=submission, question=sub_q.question,
            defaults={'marks_obtained': sq_total}
        )
    else:
        # Backward-compatible: accept entity_id or question_id
        qid = data.get('entity_id') or data.get('question_id')
        question = get_object_or_404(Question, id=qid,
                                      assessment__course__faculty=request.user)
        marks = min(max(marks, 0), question.max_marks)
        submission, _ = Submission.objects.get_or_create(
            student=student, assessment=question.assessment,
            defaults={'content': '', 'status': 'graded', 'total_score': 0,
                      'plagiarism_score': 0, 'ai_content_score': 0}
        )
        QuestionGrade.objects.update_or_create(
            submission=submission, question=question,
            defaults={'marks_obtained': marks}
        )

    total = sum(g.marks_obtained for g in QuestionGrade.objects.filter(submission=submission))
    submission.total_score = total
    if submission.status == 'submitted':
        submission.status = 'graded'
    submission.save()
    return JsonResponse({'success': True, 'marks': marks, 'total': total})


@student_required
def get_unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})
 
 
@student_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})




# QUESTION BANK VIEWS



@faculty_required
def faculty_question_bank(request):
    from .models import PastPaper
    courses = Course.objects.filter(faculty=request.user)
    papers  = PastPaper.objects.filter(
        uploaded_by=request.user
    ).prefetch_related('questions', 'allowed_courses')

    # Build assessment question bank: course → type groups → assessments → questions
    TYPE_ORDER  = ['assignment', 'quiz', 'mid', 'ct', 'final', 'lab']
    TYPE_LABELS = dict(Assessment.TYPE_CHOICES)

    def type_sort_key(t):
        try:
            return TYPE_ORDER.index(t)
        except ValueError:
            return len(TYPE_ORDER)

    course_bank = []
    for course in courses:
        assessments = Assessment.objects.filter(course=course).prefetch_related(
            'questions__clos', 'questions__plos',
            'questions__sub_questions__clos',
            'questions__sub_questions__plos',
        ).order_by('assessment_type', 'created_at')

        type_map = defaultdict(list)
        for a in assessments:
            qs = list(a.questions.all())
            if qs:
                type_map[a.assessment_type].append({'assessment': a, 'questions': qs})

        if not type_map:
            continue

        # Add num_label so template can show "Quiz 1", "Quiz 2" etc.
        for t, entries in type_map.items():
            lbl = TYPE_LABELS.get(t, t.replace('_', ' ').title())
            total = len(entries)
            for i, entry in enumerate(entries, 1):
                entry['num_label'] = f"{lbl} {i}" if total > 1 else lbl

        type_groups = [
            {
                'type_key':   t,
                'type_label': TYPE_LABELS.get(t, t.replace('_', ' ').title()),
                'entries':    type_map[t],
                'q_count':    sum(len(e['questions']) for e in type_map[t]),
            }
            for t in sorted(type_map.keys(), key=type_sort_key)
        ]
        course_bank.append({
            'course':      course,
            'type_groups': type_groups,
            'total_q':     sum(g['q_count'] for g in type_groups),
        })

    return render(request, 'faculty/question_bank.html', {
        'papers':      papers,
        'courses':     courses,
        'course_bank': course_bank,
    })


@faculty_required
def create_past_paper(request):
    from .models import PastPaper, PastPaperQuestion
    if request.method == 'POST':
        data = json.loads(request.body)
        paper = PastPaper.objects.create(
            title         = data['title'],
            course_code   = data['course_code'],
            course_name   = data['course_name'],
            semester      = data['semester'],
            exam_type     = data['exam_type'],
            total_marks   = int(data.get('total_marks', 0)),
            duration_mins = int(data.get('duration_mins', 0)),
            description   = data.get('description', ''),
            is_public     = data.get('is_public', False),
            uploaded_by   = request.user,
        )
        course_ids = data.get('allowed_course_ids', [])
        if course_ids:
            paper.allowed_courses.set(
                Course.objects.filter(id__in=course_ids, faculty=request.user)
            )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            PastPaperQuestion.objects.create(
                paper       = paper,
                order       = i,
                text        = q['text'],
                marks       = int(q.get('marks', 0)),
                answer_hint = q.get('answer_hint', ''),
                show_hint   = q.get('show_hint', False),
                topic_tag   = q.get('topic_tag', ''),
                difficulty  = q.get('difficulty', ''),
            )
            total += int(q.get('marks', 0))
        if total > 0:
            paper.total_marks = total
            paper.save(update_fields=['total_marks'])
        return JsonResponse({'success': True, 'id': paper.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_past_paper(request, paper_id):
    from .models import PastPaper
    paper = get_object_or_404(PastPaper, id=paper_id, uploaded_by=request.user)
    paper.delete()
    return JsonResponse({'success': True})


@faculty_required
def toggle_paper_visibility(request, paper_id):
    from .models import PastPaper
    paper = get_object_or_404(PastPaper, id=paper_id, uploaded_by=request.user)
    paper.is_public = not paper.is_public
    paper.save(update_fields=['is_public'])
    return JsonResponse({'success': True, 'is_public': paper.is_public})


@faculty_required
def toggle_hint_visibility(request, question_id):
    from .models import PastPaperQuestion
    q = get_object_or_404(PastPaperQuestion, id=question_id,
                          paper__uploaded_by=request.user)
    q.show_hint = not q.show_hint
    q.save(update_fields=['show_hint'])
    return JsonResponse({'success': True, 'show_hint': q.show_hint})


@student_required
def student_question_bank(request):
    from .models import PastPaper
    from django.db.models import Q

    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    enrolled_ids = [e.course_id for e in enrollments]

    # Build course bank for the Assessment Questions tab
    course_bank = []
    for e in enrollments:
        course = e.course
        assessments = Assessment.objects.filter(
            course=course, status='published'
        ).prefetch_related('questions').order_by('assessment_type', 'created_at')
        type_set = set()
        q_total = 0
        for a in assessments:
            qs = a.questions.count()
            if qs > 0:
                type_set.add(a.assessment_type)
                q_total += qs
        if q_total > 0:
            course_bank.append({
                'course':      course,
                'type_count':  len(type_set),
                'q_total':     q_total,
            })

    # Past papers (existing logic unchanged)
    papers = PastPaper.objects.filter(
        Q(is_public=True) | Q(allowed_courses__id__in=enrolled_ids)
    ).distinct().prefetch_related('questions')

    search      = request.GET.get('q', '').strip()
    exam_type   = request.GET.get('type', '')
    semester    = request.GET.get('semester', '')
    course_code = request.GET.get('course', '')
    difficulty  = request.GET.get('difficulty', '')

    if search:
        papers = papers.filter(
            Q(title__icontains=search) |
            Q(course_code__icontains=search) |
            Q(course_name__icontains=search) |
            Q(questions__text__icontains=search) |
            Q(questions__topic_tag__icontains=search)
        ).distinct()
    if exam_type:
        papers = papers.filter(exam_type=exam_type)
    if semester:
        papers = papers.filter(semester__icontains=semester)
    if course_code:
        papers = papers.filter(course_code__icontains=course_code)
    if difficulty:
        papers = papers.filter(questions__difficulty=difficulty).distinct()

    all_accessible = PastPaper.objects.filter(
        Q(is_public=True) | Q(allowed_courses__id__in=enrolled_ids)
    ).distinct()

    return render(request, 'student/question_bank.html', {
        'course_bank':  course_bank,
        'papers':       papers,
        'total_count':  papers.count(),
        'course_codes': sorted(set(all_accessible.values_list('course_code', flat=True))),
        'semesters':    sorted(set(all_accessible.values_list('semester', flat=True)), reverse=True),
        'search':       search,
        'exam_type':    exam_type,
        'semester':     semester,
        'course_code':  course_code,
        'difficulty':   difficulty,
        'active_tab':   request.GET.get('tab', 'assessments'),
    })


@student_required
def student_view_paper(request, paper_id):
    from .models import PastPaper
    from django.db.models import Q
    enrolled_ids = Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True)

    paper = get_object_or_404(PastPaper, id=paper_id)

    # Permission check
    if not paper.is_public:
        if not paper.allowed_courses.filter(id__in=enrolled_ids).exists():
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("You don't have access to this paper.")

    return render(request, 'student/view_paper.html', {
        'paper':     paper,
        'questions': paper.questions.all(),
    })


@student_required
def student_qbank_course(request, course_id):
    enrolled_ids = list(Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True))

    if course_id not in enrolled_ids:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    course = get_object_or_404(Course, id=course_id)

    TYPE_ORDER  = ['assignment', 'quiz', 'mid', 'ct', 'final', 'lab']
    TYPE_LABELS = dict(Assessment.TYPE_CHOICES)

    def type_sort_key(t):
        try:
            return TYPE_ORDER.index(t)
        except ValueError:
            return len(TYPE_ORDER)

    type_map = {}
    for a in Assessment.objects.filter(course=course, status='published').prefetch_related('questions'):
        qs = a.questions.count()
        if qs > 0:
            if a.assessment_type not in type_map:
                type_map[a.assessment_type] = {'a_count': 0, 'q_count': 0}
            type_map[a.assessment_type]['a_count'] += 1
            type_map[a.assessment_type]['q_count'] += qs

    type_groups = [
        {
            'type_key':   t,
            'type_label': TYPE_LABELS.get(t, t.replace('_', ' ').title()),
            'a_count':    type_map[t]['a_count'],
            'q_count':    type_map[t]['q_count'],
        }
        for t in sorted(type_map.keys(), key=type_sort_key)
    ]

    return render(request, 'student/qbank_course.html', {
        'course':      course,
        'type_groups': type_groups,
    })


@student_required
def student_qbank_type(request, course_id, atype):
    enrolled_ids = list(Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True))

    if course_id not in enrolled_ids:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    course = get_object_or_404(Course, id=course_id)
    TYPE_LABELS = dict(Assessment.TYPE_CHOICES)
    type_label  = TYPE_LABELS.get(atype, atype.replace('_', ' ').title())

    assessments = Assessment.objects.filter(
        course=course, assessment_type=atype, status='published'
    ).prefetch_related(
        'questions__clos',
        'questions__plos',
        'questions__sub_questions__clos',
        'questions__sub_questions__plos',
    ).order_by('created_at')

    all_with_q = [a for a in assessments if a.questions.exists()]
    total = len(all_with_q)
    entries = []
    for idx, a in enumerate(all_with_q, 1):
        entries.append({
            'assessment': a,
            'label':      f"{type_label} {idx}" if total > 1 else type_label,
            'questions':  list(a.questions.all().order_by('order')),
        })

    return render(request, 'student/qbank_type.html', {
        'course':     course,
        'atype':      atype,
        'type_label': type_label,
        'entries':    entries,
    })

# ADMIN PORTAL VIEWS

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('sign_in_html')
        if request.user.role != 'admin' and not request.user.is_superuser:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@admin_required
def admin_dashboard(request):
    from datetime import date as dt_date
    return render(request, 'admin_portal/dashboard.html', {
        'today':                dt_date.today().strftime('%B %d, %Y'),
        'total_users':          User.objects.count(),
        'total_faculty':        User.objects.filter(role='faculty').count(),
        'total_students':       User.objects.filter(role='student').count(),
        'total_courses':        Course.objects.count(),
        'total_enrollments':    Enrollment.objects.count(),
        'total_assessments':    Assessment.objects.count(),
        'published_assessments':Assessment.objects.filter(status='published').count(),
        'total_submissions':    Submission.objects.count(),
        'pending_submissions':  Submission.objects.filter(status='submitted').count(),
        'recent_users':         User.objects.order_by('-date_joined')[:6],
        'recent_courses':       Course.objects.prefetch_related('enrollments').order_by('-created_at')[:6],
        'recent_submissions':   Submission.objects.select_related('student', 'assessment__course').order_by('-submitted_at')[:8],
    })


@admin_required
def admin_users(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'admin_portal/users.html', {'users': users})


@admin_required
def admin_create_user(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email     = request.POST.get('email', '').strip()
        password  = request.POST.get('password', '')
        role      = request.POST.get('role', 'student')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('admin_users')
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('admin_users')
        username = email.split('@')[0]
        base = username; i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"; i += 1
        user = User.objects.create_user(
            username=username, email=email, password=password,
            full_name=full_name, role=role,
        )
        if role == 'admin':
            user.is_staff = True
            user.save()
        messages.success(request, f'User {full_name} created successfully.')
    return redirect('admin_users')


@admin_required
def admin_edit_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        u.full_name = request.POST.get('full_name', u.full_name).strip()
        u.email     = request.POST.get('email', u.email).strip()
        u.role      = request.POST.get('role', u.role)
        pw = request.POST.get('password', '').strip()
        if pw:
            if len(pw) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
                return redirect('admin_users')
            u.set_password(pw)
        u.is_staff = (u.role == 'admin')
        u.save()
        messages.success(request, f'User {u.full_name} updated.')
    return redirect('admin_users')


@admin_required
def admin_toggle_user(request, user_id):
    if request.method == 'POST':
        u = get_object_or_404(User, id=user_id)
        u.is_active = not u.is_active
        u.save()
        status = 'activated' if u.is_active else 'deactivated'
        messages.success(request, f'User {u.full_name or u.username} {status}.')
    return redirect('admin_users')


@admin_required
def admin_delete_user(request, user_id):
    if request.method == 'POST':
        u = get_object_or_404(User, id=user_id)
        name = u.full_name or u.username
        u.delete()
        messages.success(request, f'User {name} deleted.')
    return redirect('admin_users')


@admin_required
def admin_courses(request):
    courses = Course.objects.select_related('faculty').prefetch_related('enrollments', 'assessments').order_by('-created_at')
    semesters = Course.objects.values_list('semester', flat=True).distinct().order_by('semester')
    return render(request, 'admin_portal/courses.html', {
        'courses': courses, 'semesters': semesters,
    })


@admin_required
def admin_delete_course(request, course_id):
    if request.method == 'POST':
        c = get_object_or_404(Course, id=course_id)
        name = c.code
        c.delete()
        messages.success(request, f'Course {name} deleted.')
    return redirect('admin_courses')


@admin_required
def admin_assessments(request):
    assessments = Assessment.objects.select_related('course__faculty').prefetch_related('submissions').order_by('-created_at')
    return render(request, 'admin_portal/assessments.html', {'assessments': assessments})


@admin_required
def admin_delete_assessment(request, assessment_id):
    if request.method == 'POST':
        a = get_object_or_404(Assessment, id=assessment_id)
        title = a.title
        a.delete()
        messages.success(request, f'Assessment "{title}" deleted.')
    return redirect('admin_assessments')


@admin_required
def admin_submissions(request):
    submissions = Submission.objects.select_related('student', 'assessment__course').order_by('-submitted_at')
    return render(request, 'admin_portal/submissions.html', {'submissions': submissions})


@admin_required
def admin_announcements(request):
    announcements = Announcement.objects.select_related('course', 'created_by').order_by('-created_at')
    return render(request, 'admin_portal/announcements.html', {'announcements': announcements})


@admin_required
def admin_delete_announcement(request, ann_id):
    if request.method == 'POST':
        a = get_object_or_404(Announcement, id=ann_id)
        a.delete()
        messages.success(request, 'Announcement deleted.')
    return redirect('admin_announcements')


@admin_required
def admin_materials(request):
    materials = StudyMaterial.objects.select_related('course', 'uploaded_by').order_by('-uploaded_at')
    return render(request, 'admin_portal/materials.html', {'materials': materials})


@admin_required
def admin_delete_material(request, material_id):
    if request.method == 'POST':
        m = get_object_or_404(StudyMaterial, id=material_id)
        m.delete()
        messages.success(request, 'Material deleted.')
    return redirect('admin_materials')