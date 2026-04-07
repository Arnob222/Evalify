from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count
import json
from .models import (User, Course, CLO, PLO, Assessment, Question,
                     Enrollment, Submission, QuestionGrade, Announcement)


#Home Redirect 
def home(request):
    if not request.user.is_authenticated:
        return render(request, 'homepage.html')
    if request.user.role == 'faculty' or request.user.is_superuser:
        return redirect('faculty_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'admin':
        return redirect('faculty_dashboard')
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

        if not full_name or not email or not password:
            return render(request, 'sign_up.html', {'error': 'All fields are required.'})
        if len(password) < 8:
            return render(request, 'sign_up.html', {'error': 'Password must be at least 8 characters.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'sign_up.html', {'error': 'Email already registered.'})

        
        username = email.split('@')[0]
        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role=role,
        )
        login(request, user)
        return redirect('home')
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
    courses = Course.objects.filter(faculty=request.user)
    assessments = Assessment.objects.filter(course__in=courses)
    pending_subs = Submission.objects.filter(assessment__in=assessments, status='submitted')
    flagged_subs = Submission.objects.filter(assessment__in=assessments, status='flagged')
    recent_submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment').order_by('-submitted_at')[:8]
    announcements = Announcement.objects.filter(
        course__in=courses
    ).order_by('-created_at')[:5]

    return render(request, 'faculty/dashboard.html', {
        'courses': courses,
        'assessments_count': assessments.count(),
        'pending_count': pending_subs.count(),
        'flagged_count': flagged_subs.count(),
        'recent_submissions': recent_submissions,
        'announcements': announcements,
    })


@faculty_required
def faculty_courses(request):
    courses = Course.objects.filter(faculty=request.user).prefetch_related(
        'clos', 'clos__plos', 'enrollments', 'enrollments__student'
    )
    # PLO count per course calculate করা
    for course in courses:
        plo_ids = set()
        for clo in course.clos.all():
            for plo in clo.plos.all():
                plo_ids.add(plo.id)
        course.plo_count = len(plo_ids)
 
    plos = PLO.objects.all()
    return render(request, 'faculty/courses.html', {
        'courses': courses,
        'plos': plos,
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
    assessments = Assessment.objects.filter(course__in=courses)
    submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment__course').order_by('-submitted_at')
    return render(request, 'faculty/grading.html', {
        'submissions': submissions,
        'assessments': assessments,
        'pending': submissions.filter(status='submitted').count(),
        'graded': submissions.filter(status='graded').count(),
        'flagged': submissions.filter(status='flagged').count(),
    })


@faculty_required
def get_submission_detail(request, sub_id):
    sub = get_object_or_404(Submission, id=sub_id, assessment__course__faculty=request.user)
    questions = []
    for q in sub.assessment.questions.all():
        try:
            obtained = QuestionGrade.objects.get(submission=sub, question=q).marks_obtained
        except QuestionGrade.DoesNotExist:
            obtained = 0
        questions.append({
            'id': q.id, 'order': q.order, 'text': q.text,
            'max_marks': q.max_marks, 'obtained': obtained,
            'clos': [{'code': c.code} for c in q.clos.all()]
        })
    return JsonResponse({
        'id': sub.id,
        'student_name': sub.student.full_name or sub.student.username,
        'assessment_title': sub.assessment.title,
        'assessment_type': sub.assessment.assessment_type,
        'total_marks': sub.assessment.total_marks,
        'content': sub.content,
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
        for qg_data in data.get('question_grades', []):
            q = get_object_or_404(Question, id=qg_data['question_id'])
            marks = min(float(qg_data['marks']), q.max_marks)
            QuestionGrade.objects.update_or_create(
                submission=sub, question=q, defaults={'marks_obtained': marks}
            )
            total += marks
        status = 'flagged' if (sub.plagiarism_score > 30 or sub.ai_content_score > 50) else 'graded'
        sub.total_score = total
        sub.feedback = data.get('feedback', '')
        sub.status = status
        sub.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_analytics(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None
    grade_dist = []
    clo_attainment = []
    weak_students = []
    integrity_data = {'clean': 0, 'ai_flag': 0, 'plagiarism': 0}

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if selected_course:
        assessments = Assessment.objects.filter(course=selected_course)
        graded_subs = Submission.objects.filter(
            assessment__in=assessments, status__in=['graded', 'flagged']
        )
        ranges = [('90-100', 90, 100), ('80-89', 80, 89), ('70-79', 70, 79), ('60-69', 60, 69), ('<60', 0, 59)]
        for label, lo, hi in ranges:
            count = sum(
                1 for s in graded_subs
                if s.assessment.total_marks > 0
                and lo <= (s.total_score / s.assessment.total_marks * 100) <= hi
            )
            grade_dist.append({'label': label, 'count': count})

        for clo in selected_course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=graded_subs)
            total_possible = sum(Question.objects.get(id=qid).max_marks for qid in q_ids) * max(graded_subs.count(), 1)
            total_obtained = sum(g.marks_obtained for g in qgs)
            attainment = round((total_obtained / total_possible * 100) if total_possible > 0 else 0, 1)
            clo_attainment.append({'code': clo.code, 'attainment': attainment})

        for sub in graded_subs:
            if sub.assessment.total_marks > 0:
                pct = round(sub.total_score / sub.assessment.total_marks * 100, 1)
                if pct < 70:
                    weak_students.append({
                        'name': sub.student.full_name or sub.student.username,
                        'score': f"{int(sub.total_score)}/{sub.assessment.total_marks}",
                        'pct': pct
                    })
            if sub.plagiarism_score > 30:
                integrity_data['plagiarism'] += 1
            elif sub.ai_content_score > 50:
                integrity_data['ai_flag'] += 1
            else:
                integrity_data['clean'] += 1

    return render(request, 'faculty/analytics.html', {
        'courses': courses,
        'selected_course': selected_course,
        'grade_dist': json.dumps(grade_dist),
        'clo_attainment': json.dumps(clo_attainment),
        'weak_students': weak_students,
        'integrity_data': json.dumps(integrity_data),
    })


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
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(course__in=courses, status='published')
    submissions = Submission.objects.filter(student=request.user, assessment__in=assessments)
    submitted_ids = submissions.values_list('assessment_id', flat=True)
    pending_count = assessments.exclude(id__in=submitted_ids).count()
    graded = submissions.filter(status='graded')
    avg_grade = 0
    if graded.exists():
        total_pct = sum(
            (s.total_score / s.assessment.total_marks * 100)
            for s in graded if s.assessment.total_marks > 0
        )
        avg_grade = round(total_pct / graded.count(), 1)
    recent_grades = graded.select_related('assessment').order_by('-submitted_at')[:5]
    announcements = Announcement.objects.filter(course__in=courses).order_by('-created_at')[:5]
    return render(request, 'student/dashboard.html', {
        'courses': courses,
        'submissions_count': submissions.count(),
        'pending_count': pending_count,
        'avg_grade': avg_grade,
        'recent_grades': recent_grades,
        'announcements': announcements,
    })


@student_required
def student_courses(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    enrolled_ids = [e.course_id for e in enrollments]
    courses = []
    for e in enrollments:
        c = e.course
        c.clos_list = c.clos.prefetch_related('plos').all()
        c.assignment_count = Assessment.objects.filter(course=c, status='published').count()
        courses.append(c)
    all_courses = Course.objects.exclude(id__in=enrolled_ids)
    return render(request, 'student/courses.html', {
        'courses': courses, 'all_courses': all_courses
    })


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
    pending_assessments = assessments.exclude(id__in=submitted_ids)
    return render(request, 'student/submissions.html', {
        'submissions': submissions,
        'pending_assessments': pending_assessments,
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
        results.append({
            'course': course, 'grade': grade,
            'avg_pct': avg_pct, 'graded_count': subs.count(),
            'clo_results': clo_results,
        })
    return render(request, 'student/clo_results.html', {'results': results})


@student_required
def student_notifications(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses = [e.course for e in enrollments]
    announcements = Announcement.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-created_at')
    return render(request, 'student/notifications.html', {'announcements': announcements})



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