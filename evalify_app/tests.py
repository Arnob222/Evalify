# tests.py — Unit tests for evalify_app
# Covers: models, grace_period, notifications, auth views,
#          faculty views, student views, and permission checks.

import json
import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from evalify_app.models import (
    Course, CLO, PLO, Assessment, Question, SubQuestion,
    Enrollment, Submission, QuestionGrade, SubQuestionGrade,
    StudyMaterial, Announcement, Notification,
    PastPaper, PastPaperQuestion, CLOActionPlan, PLOActionPlan,
)
from evalify_app.grace_period import (
    get_deadline_dt, get_grace_deadline,
    check_submission_window, calculate_deduction,
    apply_late_deduction, recalculate_final_score,
)
from evalify_app.notifications import (
    notify_grade_released, notify_new_assignment,
    notify_new_material, notify_announcement,
    send_deadline_reminders,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Base setup
# ─────────────────────────────────────────────────────────────────────────────
class BaseTestCase(TestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            username='faculty1', email='john.doe@uap-bd.edu',
            password='pass12345', role='faculty', full_name='Dr. Smith',
        )
        self.student = User.objects.create_user(
            username='20220001', email='20220001@uap-bd.edu',
            password='pass12345', role='student', full_name='Alice',
        )
        self.faculty_client = Client()
        self.faculty_client.login(username='faculty1', password='pass12345')
        self.student_client = Client()
        self.student_client.login(username='20220001', password='pass12345')

        self.course = Course.objects.create(
            code='CS101', name='Intro to CS',
            faculty=self.faculty, semester='Fall 2025', credit_hours=3,
        )
        self.plo = PLO.objects.create(
            code='PLO1', description='Problem Solving', created_by=self.faculty,
        )
        self.clo = CLO.objects.create(
            course=self.course, code='CLO1',
            description='Write algorithms', bloom_level='Apply (L3)',
        )
        self.clo.plos.add(self.plo)


# ─────────────────────────────────────────────────────────────────────────────
# 1. MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────
class UserModelTests(BaseTestCase):
    def test_str_with_full_name(self):
        self.assertEqual(str(self.faculty), 'Dr. Smith (faculty)')

    def test_str_without_full_name(self):
        u = User.objects.create_user(username='bare', password='x', role='student')
        # full_name is '' (falsy), so __str__ falls back to username
        self.assertEqual(str(u), 'bare (student)')

    def test_role_faculty(self):
        self.assertEqual(self.faculty.role, 'faculty')

    def test_role_student(self):
        self.assertEqual(self.student.role, 'student')

    def test_username_unique(self):
        with self.assertRaises(Exception):
            User.objects.create_user(username='faculty1', password='x')


class CourseModelTests(BaseTestCase):
    def test_str(self):
        self.assertEqual(str(self.course), 'CS101: Intro to CS')

    def test_faculty_relationship(self):
        self.assertEqual(self.course.faculty, self.faculty)

    def test_clos_relation(self):
        self.assertEqual(self.course.clos.count(), 1)

    def test_enrollments_count_after_enroll(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assertEqual(self.course.enrollments.count(), 1)


class CLOPLOModelTests(BaseTestCase):
    def test_clo_str(self):
        self.assertEqual(str(self.clo), 'CS101 - CLO1')

    def test_plo_str(self):
        self.assertEqual(str(self.plo), 'PLO1')

    def test_clo_plo_m2m(self):
        self.assertIn(self.plo, self.clo.plos.all())

    def test_plo_created_by(self):
        self.assertEqual(self.plo.created_by, self.faculty)


class AssessmentModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.assessment = Assessment.objects.create(
            course=self.course, title='Midterm',
            assessment_type='mid', total_marks=50, status='published',
        )

    def test_str(self):
        self.assertEqual(str(self.assessment), 'Midterm (CS101)')

    def test_assessment_type(self):
        self.assertEqual(self.assessment.assessment_type, 'mid')

    def test_default_status_is_published(self):
        a = Assessment.objects.create(
            course=self.course, title='X', assessment_type='quiz',
        )
        self.assertEqual(a.status, 'published')

    def test_cascade_delete_questions(self):
        q = Question.objects.create(
            assessment=self.assessment, order=1, text='Q?', max_marks=10,
        )
        self.assessment.delete()
        self.assertFalse(Question.objects.filter(id=q.id).exists())


class QuestionSubQuestionModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.assessment = Assessment.objects.create(
            course=self.course, title='Quiz', assessment_type='quiz',
        )
        self.question = Question.objects.create(
            assessment=self.assessment, order=1, text='What is 2+2?', max_marks=5,
        )

    def test_question_str(self):
        self.assertEqual(str(self.question), 'Q1 - Quiz')

    def test_subquestion_str(self):
        sq = SubQuestion.objects.create(
            question=self.question, order=1, text='Part a', max_marks=2,
        )
        self.assertEqual(str(sq), 'Sub-Q1 of Q1 (Quiz)')

    def test_question_clos_m2m(self):
        self.question.clos.add(self.clo)
        self.assertIn(self.clo, self.question.clos.all())

    def test_question_plos_m2m(self):
        self.question.plos.add(self.plo)
        self.assertIn(self.plo, self.question.plos.all())


class EnrollmentModelTests(BaseTestCase):
    def test_create_enrollment(self):
        e = Enrollment.objects.create(student=self.student, course=self.course)
        self.assertEqual(e.student, self.student)
        self.assertEqual(e.course, self.course)

    def test_unique_together(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(student=self.student, course=self.course)

    def test_cascade_delete_on_course_delete(self):
        e = Enrollment.objects.create(student=self.student, course=self.course)
        course2 = Course.objects.create(
            code='CS999', name='Tmp', faculty=self.faculty, semester='X',
        )
        e2 = Enrollment.objects.create(student=self.student, course=course2)
        course2.delete()
        self.assertFalse(Enrollment.objects.filter(id=e2.id).exists())
        self.assertTrue(Enrollment.objects.filter(id=e.id).exists())


class SubmissionModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.assessment = Assessment.objects.create(
            course=self.course, title='HW1', assessment_type='assignment',
        )

    def test_default_status_submitted(self):
        sub = Submission.objects.create(
            student=self.student, assessment=self.assessment,
        )
        self.assertEqual(sub.status, 'submitted')

    def test_default_scores_zero(self):
        sub = Submission.objects.create(
            student=self.student, assessment=self.assessment,
        )
        self.assertEqual(sub.total_score, 0)
        self.assertEqual(sub.final_score, 0)
        self.assertEqual(sub.late_deduction, 0)

    def test_unique_together(self):
        Submission.objects.create(student=self.student, assessment=self.assessment)
        with self.assertRaises(IntegrityError):
            Submission.objects.create(student=self.student, assessment=self.assessment)

    def test_is_late_default_false(self):
        sub = Submission.objects.create(
            student=self.student, assessment=self.assessment,
        )
        self.assertFalse(sub.is_late)


class QuestionGradeModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        assessment = Assessment.objects.create(
            course=self.course, title='Q', assessment_type='quiz',
        )
        self.question = Question.objects.create(
            assessment=assessment, order=1, text='Q?', max_marks=10,
        )
        self.submission = Submission.objects.create(
            student=self.student, assessment=assessment,
        )

    def test_create_question_grade(self):
        qg = QuestionGrade.objects.create(
            submission=self.submission, question=self.question, marks_obtained=7,
        )
        self.assertEqual(qg.marks_obtained, 7)

    def test_unique_together(self):
        QuestionGrade.objects.create(
            submission=self.submission, question=self.question, marks_obtained=5,
        )
        with self.assertRaises(IntegrityError):
            QuestionGrade.objects.create(
                submission=self.submission, question=self.question, marks_obtained=8,
            )


class StudyMaterialModelTests(BaseTestCase):
    def test_filename_with_file(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Notes',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        mat.file.name = 'materials/lecture_notes.pdf'
        self.assertEqual(mat.filename(), 'lecture_notes.pdf')

    def test_filename_without_file(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Empty',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        self.assertEqual(mat.filename(), '')

    def test_is_video_by_type(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Vid',
            material_type='video', uploaded_by=self.faculty,
        )
        self.assertTrue(mat.is_video())

    def test_is_video_by_url(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Vid2',
            material_type='lecture_note',
            video_url='https://youtube.com/watch?v=abc',
            uploaded_by=self.faculty,
        )
        self.assertTrue(mat.is_video())

    def test_is_not_video(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Note',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        self.assertFalse(mat.is_video())

    def test_embed_url_watch_format(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='YT Watch',
            material_type='video',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            uploaded_by=self.faculty,
        )
        self.assertEqual(mat.embed_url(), 'https://www.youtube.com/embed/dQw4w9WgXcQ')

    def test_embed_url_youtu_be_format(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='YT Short',
            material_type='video',
            video_url='https://youtu.be/dQw4w9WgXcQ',
            uploaded_by=self.faculty,
        )
        self.assertEqual(mat.embed_url(), 'https://www.youtube.com/embed/dQw4w9WgXcQ')

    def test_embed_url_empty(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='No Vid',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        self.assertEqual(mat.embed_url(), '')

    def test_is_visible_default_true(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Vis',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        self.assertTrue(mat.is_visible)

    def test_str(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Lec1',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        self.assertEqual(str(mat), 'Lec1 (CS101)')


class NotificationModelTests(BaseTestCase):
    def test_notification_send_creates_record(self):
        Notification.send(
            recipient=self.student,
            notif_type='grade_released',
            title='Test Notif',
            message='Your grade is out.',
        )
        self.assertEqual(Notification.objects.filter(recipient=self.student).count(), 1)

    def test_notification_send_deduplication_within_one_minute(self):
        for _ in range(3):
            Notification.send(
                recipient=self.student,
                notif_type='grade_released',
                title='Same Title',
                message='Same message.',
            )
        # Only one should be created due to dedup
        self.assertEqual(
            Notification.objects.filter(recipient=self.student, title='Same Title').count(), 1,
        )

    def test_notification_default_is_read_false(self):
        n = Notification.objects.create(
            recipient=self.student,
            notif_type='new_assignment',
            title='N', message='m',
        )
        self.assertFalse(n.is_read)

    def test_notification_str(self):
        n = Notification.objects.create(
            recipient=self.student,
            notif_type='new_assignment',
            title='NotifTitle', message='msg',
        )
        self.assertIn('new_assignment', str(n))
        self.assertIn(self.student.username, str(n))


class PastPaperModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.paper = PastPaper.objects.create(
            title='Mid Fall 2024',
            course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='mid',
            uploaded_by=self.faculty, is_public=True,
        )

    def test_str(self):
        self.assertEqual(str(self.paper), 'CS101 | Fall 2024 | Mid Exam')

    def test_default_total_marks_zero(self):
        self.assertEqual(self.paper.total_marks, 0)

    def test_is_public(self):
        self.assertTrue(self.paper.is_public)


class PastPaperQuestionModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.paper = PastPaper.objects.create(
            title='Q Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='final', uploaded_by=self.faculty,
        )

    def test_str(self):
        q = PastPaperQuestion.objects.create(
            paper=self.paper, order=1, text='Explain OOP', marks=10, difficulty='medium',
        )
        self.assertIn('Q1', str(q))

    def test_default_show_hint_false(self):
        q = PastPaperQuestion.objects.create(
            paper=self.paper, order=1, text='Q?', marks=5,
        )
        self.assertFalse(q.show_hint)


class ActionPlanModelTests(BaseTestCase):
    def test_clo_action_plan_unique_together(self):
        CLOActionPlan.objects.create(course=self.course, clo=self.clo, action_plan='Plan A')
        with self.assertRaises(IntegrityError):
            CLOActionPlan.objects.create(course=self.course, clo=self.clo, action_plan='Plan B')

    def test_plo_action_plan_unique_together(self):
        PLOActionPlan.objects.create(course=self.course, plo=self.plo, action_plan='Plan X')
        with self.assertRaises(IntegrityError):
            PLOActionPlan.objects.create(course=self.course, plo=self.plo, action_plan='Plan Y')

    def test_clo_action_plan_get_or_create(self):
        obj, created = CLOActionPlan.objects.get_or_create(
            course=self.course, clo=self.clo, defaults={'action_plan': 'Init'},
        )
        self.assertTrue(created)
        obj2, created2 = CLOActionPlan.objects.get_or_create(
            course=self.course, clo=self.clo, defaults={'action_plan': 'Other'},
        )
        self.assertFalse(created2)
        self.assertEqual(obj.id, obj2.id)


# ─────────────────────────────────────────────────────────────────────────────
# 2. GRACE PERIOD TESTS
# ─────────────────────────────────────────────────────────────────────────────
class GracePeriodTests(BaseTestCase):
    def _make_assessment(self, due_days_offset=0, grace_hours=0,
                          deduction_type='percent', deduction_value=10,
                          max_late_days=0, total_marks=100):
        due_date = (timezone.now() + datetime.timedelta(days=due_days_offset)).date() \
            if due_days_offset is not None else None
        return Assessment.objects.create(
            course=self.course, title='Test', assessment_type='assignment',
            due_date=due_date, status='published',
            grace_period_hours=grace_hours,
            late_deduction_type=deduction_type,
            late_deduction_value=deduction_value,
            max_late_days=max_late_days,
            total_marks=total_marks,
        )

    def test_get_deadline_dt_no_due_date(self):
        a = self._make_assessment(due_days_offset=None)
        a.due_date = None
        self.assertIsNone(get_deadline_dt(a))

    def test_get_deadline_dt_with_due_date(self):
        a = self._make_assessment(due_days_offset=1)
        dt = get_deadline_dt(a)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.date(), a.due_date)

    def test_get_grace_deadline_no_due_date(self):
        a = self._make_assessment(due_days_offset=None)
        a.due_date = None
        self.assertIsNone(get_grace_deadline(a))

    def test_get_grace_deadline_with_grace(self):
        a = self._make_assessment(due_days_offset=1, grace_hours=6)
        dl = get_deadline_dt(a)
        gl = get_grace_deadline(a)
        self.assertEqual((gl - dl).total_seconds(), 6 * 3600)

    def test_check_submission_window_no_deadline(self):
        a = self._make_assessment(due_days_offset=None)
        a.due_date = None
        result = check_submission_window(a)
        self.assertTrue(result['can_submit'])
        self.assertFalse(result['is_late'])
        self.assertIn('No deadline', result['window_msg'])

    def test_check_submission_window_before_deadline(self):
        a = self._make_assessment(due_days_offset=2)
        result = check_submission_window(a)
        self.assertTrue(result['can_submit'])
        self.assertFalse(result['is_late'])

    def test_check_submission_window_within_grace(self):
        # Due yesterday, but 48-hour grace period
        a = self._make_assessment(due_days_offset=-1, grace_hours=48)
        result = check_submission_window(a)
        self.assertTrue(result['can_submit'])
        self.assertTrue(result['is_late'])
        self.assertIn('Grace', result['window_msg'])

    def test_check_submission_window_past_grace_within_max(self):
        # Due 3 days ago, grace 0 hours, max_late_days=5
        a = self._make_assessment(due_days_offset=-3, grace_hours=0, max_late_days=5)
        result = check_submission_window(a)
        self.assertTrue(result['can_submit'])
        self.assertTrue(result['is_late'])

    def test_check_submission_window_past_max_late_days(self):
        # Due 10 days ago, max_late_days=3
        a = self._make_assessment(due_days_offset=-10, grace_hours=0, max_late_days=3)
        result = check_submission_window(a)
        self.assertFalse(result['can_submit'])
        self.assertTrue(result['is_late'])

    def test_check_submission_window_no_grace_no_max_past_deadline(self):
        # Due 1 day ago, no grace, no max_late_days
        a = self._make_assessment(due_days_offset=-1, grace_hours=0, max_late_days=0)
        result = check_submission_window(a)
        self.assertFalse(result['can_submit'])
        self.assertTrue(result['is_late'])

    def test_calculate_deduction_zero_hours_late(self):
        a = self._make_assessment(deduction_value=10, total_marks=100)
        self.assertEqual(calculate_deduction(a, 0), 0.0)

    def test_calculate_deduction_percent(self):
        # 2 days late, 10% per day, total_marks=100
        a = self._make_assessment(
            due_days_offset=-2, grace_hours=0,
            deduction_type='percent', deduction_value=10,
            max_late_days=0, total_marks=100,
        )
        # 48 hours late → 2 days → 2 * 10% * 100 = 20
        deduction = calculate_deduction(a, 48)
        self.assertEqual(deduction, 20.0)

    def test_calculate_deduction_flat(self):
        # 2 days late, flat 5 marks/day
        a = self._make_assessment(
            due_days_offset=-2, grace_hours=0,
            deduction_type='flat', deduction_value=5,
            max_late_days=0, total_marks=100,
        )
        deduction = calculate_deduction(a, 48)
        self.assertEqual(deduction, 10.0)

    def test_calculate_deduction_within_grace(self):
        # 12 hours late, 24-hour grace → 0 deduction
        a = self._make_assessment(grace_hours=24, deduction_value=10, total_marks=100)
        self.assertEqual(calculate_deduction(a, 12), 0.0)

    def test_calculate_deduction_capped_at_total_marks(self):
        # Huge deduction should not exceed total_marks
        a = self._make_assessment(
            deduction_type='flat', deduction_value=200, max_late_days=0, total_marks=50,
        )
        deduction = calculate_deduction(a, 100)
        self.assertLessEqual(deduction, 50.0)

    def test_apply_late_deduction_updates_submission(self):
        a = self._make_assessment(
            due_days_offset=-2, grace_hours=0,
            deduction_type='flat', deduction_value=5,
            max_late_days=5, total_marks=100,
        )
        sub = Submission.objects.create(
            student=self.student, assessment=a,
            total_score=80,
        )
        apply_late_deduction(sub)
        sub.refresh_from_db()
        self.assertTrue(sub.is_late)
        self.assertGreater(sub.late_deduction, 0)
        self.assertEqual(sub.final_score, max(0.0, sub.total_score - sub.late_deduction))

    def test_recalculate_final_score(self):
        a = self._make_assessment(total_marks=100)
        sub = Submission.objects.create(
            student=self.student, assessment=a,
            total_score=70, late_deduction=10,
        )
        recalculate_final_score(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.final_score, 60.0)

    def test_recalculate_final_score_not_below_zero(self):
        a = self._make_assessment(total_marks=100)
        sub = Submission.objects.create(
            student=self.student, assessment=a,
            total_score=5, late_deduction=50,
        )
        recalculate_final_score(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.final_score, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# 3. NOTIFICATION FUNCTION TESTS
# ─────────────────────────────────────────────────────────────────────────────
class NotificationFunctionTests(BaseTestCase):
    def _make_graded_submission(self, score=40):
        assessment = Assessment.objects.create(
            course=self.course, title='Graded HW', assessment_type='assignment',
            total_marks=50, status='published',
        )
        sub = Submission.objects.create(
            student=self.student, assessment=assessment,
            total_score=score, status='graded',
        )
        return sub

    def test_notify_grade_released_creates_notification(self):
        sub = self._make_graded_submission()
        Notification.objects.filter(recipient=self.student).delete()
        notify_grade_released(sub)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student, notif_type='grade_released',
            ).count(), 1,
        )

    def test_notify_grade_released_message_contains_score(self):
        sub = self._make_graded_submission(score=40)
        Notification.objects.filter(recipient=self.student).delete()
        notify_grade_released(sub)
        n = Notification.objects.get(recipient=self.student, notif_type='grade_released')
        self.assertIn('40', n.message)

    def test_notify_new_assignment_creates_for_enrolled(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        assessment = Assessment.objects.create(
            course=self.course, title='Assignment 1',
            assessment_type='assignment', total_marks=20, status='published',
        )
        Notification.objects.filter(recipient=self.student).delete()
        notify_new_assignment(assessment)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='new_assignment',
            ).exists()
        )

    def test_notify_new_assignment_not_sent_to_unenrolled(self):
        other = User.objects.create_user(
            username='20220002', email='20220002@uap-bd.edu',
            password='x', role='student',
        )
        assessment = Assessment.objects.create(
            course=self.course, title='Assignment 2',
            assessment_type='assignment', total_marks=20, status='published',
        )
        Notification.objects.filter(recipient=other).delete()
        notify_new_assignment(assessment)
        self.assertFalse(
            Notification.objects.filter(recipient=other, notif_type='new_assignment').exists()
        )

    def test_notify_new_material_creates_for_enrolled(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        mat = StudyMaterial.objects.create(
            course=self.course, title='Lecture 1',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        Notification.objects.filter(recipient=self.student).delete()
        notify_new_material(mat)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='new_material',
            ).exists()
        )

    def test_notify_announcement_creates_for_enrolled(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        ann = Announcement.objects.create(
            course=self.course, title='No class',
            content='Monday off', priority='high', created_by=self.faculty,
        )
        Notification.objects.filter(recipient=self.student).delete()
        notify_announcement(ann)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='announcement',
            ).exists()
        )

    def test_send_deadline_reminders_due_today(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        today = timezone.now().date()
        assessment = Assessment.objects.create(
            course=self.course, title='Due Today',
            assessment_type='assignment', due_date=today,
            total_marks=10, status='published',
        )
        Notification.objects.filter(recipient=self.student).delete()
        send_deadline_reminders()
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='deadline_today',
            ).exists()
        )

    def test_send_deadline_reminders_due_tomorrow(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        tomorrow = (timezone.now() + datetime.timedelta(days=1)).date()
        assessment = Assessment.objects.create(
            course=self.course, title='Due Tomorrow',
            assessment_type='assignment', due_date=tomorrow,
            total_marks=10, status='published',
        )
        Notification.objects.filter(recipient=self.student).delete()
        send_deadline_reminders()
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='deadline_tomorrow',
            ).exists()
        )

    def test_send_deadline_reminders_skips_submitted(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        today = timezone.now().date()
        assessment = Assessment.objects.create(
            course=self.course, title='Due Today Already Done',
            assessment_type='assignment', due_date=today,
            total_marks=10, status='published',
        )
        Submission.objects.create(student=self.student, assessment=assessment)
        Notification.objects.filter(recipient=self.student, notif_type='deadline_today').delete()
        send_deadline_reminders()
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.student, notif_type='deadline_today',
                title__contains='Due Today Already Done',
            ).exists()
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. AUTH VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────
class AuthViewTests(BaseTestCase):
    def test_home_unauthenticated_renders_homepage(self):
        c = Client()
        response = c.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'homepage.html')

    def test_home_faculty_redirects_to_dashboard(self):
        response = self.faculty_client.get(reverse('home'))
        self.assertRedirects(response, reverse('faculty_dashboard'))

    def test_home_student_redirects_to_dashboard(self):
        response = self.student_client.get(reverse('home'))
        self.assertRedirects(response, reverse('student_dashboard'))

    def test_signin_get(self):
        c = Client()
        response = c.get(reverse('sign_in_html'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sign_in.html')

    def test_signin_authenticated_redirects(self):
        response = self.faculty_client.get(reverse('sign_in_html'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_signin_post_faculty_success(self):
        c = Client()
        response = c.post(reverse('sign_in_html'), {
            'email': 'john.doe@uap-bd.edu', 'password': 'pass12345',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_signin_post_student_success(self):
        c = Client()
        response = c.post(reverse('sign_in_html'), {
            'email': '20220001@uap-bd.edu', 'password': 'pass12345',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_signin_post_wrong_password(self):
        c = Client()
        response = c.post(reverse('sign_in_html'), {
            'email': 'john.doe@uap-bd.edu', 'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid')

    def test_signin_post_nonexistent_email(self):
        c = Client()
        response = c.post(reverse('sign_in_html'), {
            'email': 'nobody@uap-bd.edu', 'password': 'pass12345',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid')

    def test_signup_get(self):
        c = Client()
        response = c.get(reverse('sign_up_html'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sign_up.html')

    def test_signup_authenticated_redirects(self):
        response = self.faculty_client.get(reverse('sign_up_html'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_signup_post_student_valid_email(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Bob Student',
            'email': '20221001@uap-bd.edu',
            'password': 'securePass1',
            'role': 'student',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email='20221001@uap-bd.edu').exists())

    def test_signup_post_faculty_valid_email(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Prof New',
            'email': 'prof.new@uap-bd.edu',
            'password': 'securePass2',
            'role': 'faculty',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email='prof.new@uap-bd.edu').exists())

    def test_signup_post_student_invalid_domain(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Bad Student',
            'email': 'student@gmail.com',
            'password': 'securePass3',
            'role': 'student',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'uap-bd.edu')

    def test_signup_post_faculty_invalid_domain(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Bad Faculty',
            'email': 'faculty@gmail.com',
            'password': 'securePass4',
            'role': 'faculty',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'uap-bd.edu')

    def test_signup_post_student_non_digit_local(self):
        """Student email must be digits@uap-bd.edu."""
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Bad', 'email': 'name@uap-bd.edu',
            'password': 'securePass5', 'role': 'student',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'digits')

    def test_signup_post_duplicate_email_shows_error(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Dup', 'email': 'john.doe@uap-bd.edu',
            'password': 'pass12345', 'role': 'faculty',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already')

    def test_signup_post_short_password(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'Short', 'email': '20221099@uap-bd.edu',
            'password': 'abc', 'role': 'student',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '8 characters')

    def test_signup_post_empty_fields(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': '', 'email': '', 'password': '', 'role': 'student',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'required')

    def test_signup_post_invalid_role(self):
        c = Client()
        response = c.post(reverse('sign_up_html'), {
            'full_name': 'X', 'email': 'x@uap-bd.edu',
            'password': 'pass12345', 'role': 'superuser',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid role')

    def test_signout_logs_out_and_redirects(self):
        response = self.faculty_client.get(reverse('sign_out'))
        self.assertRedirects(response, reverse('sign_in_html'))


# ─────────────────────────────────────────────────────────────────────────────
# 5. FACULTY VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────
class FacultyDashboardTests(BaseTestCase):
    def test_dashboard_200(self):
        response = self.faculty_client.get(reverse('faculty_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'faculty/dashboard.html')

    def test_dashboard_context_has_courses(self):
        response = self.faculty_client.get(reverse('faculty_dashboard'))
        self.assertIn('courses', response.context)

    def test_dashboard_context_counts(self):
        response = self.faculty_client.get(reverse('faculty_dashboard'))
        for key in ('assessments_count', 'pending_count', 'flagged_count'):
            self.assertIn(key, response.context)

    def test_dashboard_shows_only_own_courses(self):
        other_faculty = User.objects.create_user(
            username='other.faculty', email='other.faculty@uap-bd.edu',
            password='pass12345', role='faculty',
        )
        Course.objects.create(
            code='OTHER101', name='Other Course',
            faculty=other_faculty, semester='Fall 2025',
        )
        response = self.faculty_client.get(reverse('faculty_dashboard'))
        course_codes = [c.code for c in response.context['courses']]
        self.assertIn('CS101', course_codes)
        self.assertNotIn('OTHER101', course_codes)


class FacultyCoursesViewTests(BaseTestCase):
    def test_courses_200(self):
        response = self.faculty_client.get(reverse('faculty_courses'))
        self.assertEqual(response.status_code, 200)

    def test_add_course_success(self):
        response = self.faculty_client.post(
            reverse('add_course'),
            data=json.dumps({'code': 'CS201', 'name': 'Data Structures',
                             'semester': 'Spring 2025', 'credit_hours': 3}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(Course.objects.filter(code='CS201').exists())

    def test_add_course_creates_with_correct_faculty(self):
        self.faculty_client.post(
            reverse('add_course'),
            data=json.dumps({'code': 'CS301', 'name': 'Algorithms',
                             'semester': 'Fall 2025', 'credit_hours': 3}),
            content_type='application/json',
        )
        course = Course.objects.get(code='CS301')
        self.assertEqual(course.faculty, self.faculty)

    def test_add_course_get_returns_400(self):
        response = self.faculty_client.get(reverse('add_course'))
        self.assertEqual(response.status_code, 400)

    def test_add_clo_success(self):
        response = self.faculty_client.post(
            reverse('add_clo', args=[self.course.id]),
            data=json.dumps({
                'description': 'Design algorithms', 'bloom_level': 'Analyze (L4)',
                'plo_ids': [self.plo.id],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(CLO.objects.filter(description='Design algorithms').exists())

    def test_add_clo_assigns_plo(self):
        self.faculty_client.post(
            reverse('add_clo', args=[self.course.id]),
            data=json.dumps({
                'description': 'Apply sorting', 'bloom_level': 'Apply (L3)',
                'plo_ids': [self.plo.id],
            }),
            content_type='application/json',
        )
        clo = CLO.objects.get(description='Apply sorting')
        self.assertIn(self.plo, clo.plos.all())

    def test_delete_clo_success(self):
        clo = CLO.objects.create(
            course=self.course, code='CLO2',
            description='Temp CLO', bloom_level='Remember (L1)',
        )
        response = self.faculty_client.post(reverse('delete_clo', args=[clo.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(CLO.objects.filter(id=clo.id).exists())

    def test_get_course_clos_returns_json(self):
        response = self.faculty_client.get(
            reverse('get_course_clos', args=[self.course.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('clos', data)
        self.assertIsInstance(data['clos'], list)

    def test_add_student_to_course_success(self):
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({'email': self.student.email}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_add_student_to_course_not_found(self):
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({'email': 'nobody@uap-bd.edu'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_add_students_by_range(self):
        for reg in range(20220010, 20220013):
            User.objects.create_user(
                username=str(reg), email=f'{reg}@uap-bd.edu',
                password='pass', role='student',
            )
        response = self.faculty_client.post(
            reverse('add_students_by_range', args=[self.course.id]),
            data=json.dumps({'from_id': 20220010, 'to_id': 20220012}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['added'], 3)

    def test_add_students_by_range_from_gt_to_error(self):
        response = self.faculty_client.post(
            reverse('add_students_by_range', args=[self.course.id]),
            data=json.dumps({'from_id': 100, 'to_id': 50}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_add_plo_success(self):
        response = self.faculty_client.post(
            reverse('add_plo'),
            data=json.dumps({'description': 'Critical Thinking'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(PLO.objects.filter(description='Critical Thinking').exists())

    def test_add_plo_no_description(self):
        response = self.faculty_client.post(
            reverse('add_plo'),
            data=json.dumps({'description': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())


class FacultyAssignmentsViewTests(BaseTestCase):
    def test_assignments_list_200(self):
        response = self.faculty_client.get(reverse('faculty_assignments'))
        self.assertEqual(response.status_code, 200)

    def test_assignments_with_course_param(self):
        response = self.faculty_client.get(
            reverse('faculty_assignments') + f'?course={self.course.id}'
        )
        self.assertEqual(response.status_code, 200)

    def test_create_assignment_success(self):
        response = self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'HW1',
                'assessment_type': 'assignment',
                'due_date': '2025-12-31',
                'publish_immediately': True,
                'questions': [{'text': 'Q1', 'max_marks': 10}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(Assessment.objects.filter(title='HW1').exists())

    def test_create_assignment_creates_questions(self):
        self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'HW With Questions',
                'assessment_type': 'assignment',
                'due_date': '2025-12-31',
                'questions': [
                    {'text': 'Q1', 'max_marks': 10},
                    {'text': 'Q2', 'max_marks': 20},
                ],
            }),
            content_type='application/json',
        )
        assessment = Assessment.objects.get(title='HW With Questions')
        self.assertEqual(assessment.questions.count(), 2)
        self.assertEqual(assessment.total_marks, 30)

    def test_create_assignment_draft(self):
        self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Draft Quiz',
                'assessment_type': 'quiz',
                'publish_immediately': False,
            }),
            content_type='application/json',
        )
        assessment = Assessment.objects.get(title='Draft Quiz')
        self.assertEqual(assessment.status, 'draft')

    def test_create_assignment_published_sends_notification(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        Notification.objects.all().delete()
        self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Notify HW',
                'assessment_type': 'assignment',
                'publish_immediately': True,
            }),
            content_type='application/json',
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='new_assignment',
            ).exists()
        )

    def test_delete_assignment_success(self):
        assessment = Assessment.objects.create(
            course=self.course, title='To Delete',
            assessment_type='assignment', status='draft',
        )
        response = self.faculty_client.post(
            reverse('delete_assignment', args=[assessment.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(Assessment.objects.filter(id=assessment.id).exists())

    def test_publish_assessment_changes_status(self):
        assessment = Assessment.objects.create(
            course=self.course, title='Publish Me',
            assessment_type='quiz', status='draft',
        )
        response = self.faculty_client.post(
            reverse('publish_assessment', args=[assessment.id])
        )
        self.assertEqual(response.status_code, 200)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 'published')

    def test_publish_assessment_sends_notification(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        assessment = Assessment.objects.create(
            course=self.course, title='Pub Notif Test',
            assessment_type='quiz', status='draft',
        )
        Notification.objects.all().delete()
        self.faculty_client.post(reverse('publish_assessment', args=[assessment.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='new_assignment',
            ).exists()
        )


class FacultyGradingViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.assessment = Assessment.objects.create(
            course=self.course, title='Quiz1',
            assessment_type='quiz', total_marks=20, status='published',
        )
        self.question = Question.objects.create(
            assessment=self.assessment, order=1, text='Q?', max_marks=20,
        )
        self.submission = Submission.objects.create(
            student=self.student, assessment=self.assessment,
            content='My answer', status='submitted',
        )

    def test_grading_list_200(self):
        response = self.faculty_client.get(reverse('faculty_grading'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'faculty/grading.html')

    def test_grading_context_has_submissions(self):
        response = self.faculty_client.get(reverse('faculty_grading'))
        self.assertIn('submissions', response.context)

    def test_get_submission_detail_json(self):
        response = self.faculty_client.get(
            reverse('submission_detail', args=[self.submission.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.submission.id)
        self.assertIn('questions', data)
        self.assertEqual(data['student_name'], self.student.full_name)

    def test_grade_submission_graded(self):
        response = self.faculty_client.post(
            reverse('grade_submission', args=[self.submission.id]),
            data=json.dumps({
                'question_grades': [
                    {'question_id': self.question.id, 'marks': 15}
                ],
                'sub_question_grades': [],
                'feedback': 'Good job',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'graded')
        self.assertEqual(self.submission.total_score, 15)

    def test_grade_submission_marks_capped(self):
        """Marks cannot exceed question max_marks."""
        self.faculty_client.post(
            reverse('grade_submission', args=[self.submission.id]),
            data=json.dumps({
                'question_grades': [
                    {'question_id': self.question.id, 'marks': 999}
                ],
                'sub_question_grades': [],
                'feedback': '',
            }),
            content_type='application/json',
        )
        qg = QuestionGrade.objects.get(submission=self.submission, question=self.question)
        self.assertLessEqual(qg.marks_obtained, self.question.max_marks)

    def test_grade_submission_flagged_on_plagiarism(self):
        self.submission.plagiarism_score = 80
        self.submission.save()
        self.faculty_client.post(
            reverse('grade_submission', args=[self.submission.id]),
            data=json.dumps({
                'question_grades': [{'question_id': self.question.id, 'marks': 10}],
                'sub_question_grades': [], 'feedback': '',
            }),
            content_type='application/json',
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'flagged')

    def test_grade_submission_creates_question_grade(self):
        self.faculty_client.post(
            reverse('grade_submission', args=[self.submission.id]),
            data=json.dumps({
                'question_grades': [{'question_id': self.question.id, 'marks': 18}],
                'sub_question_grades': [], 'feedback': 'Ok',
            }),
            content_type='application/json',
        )
        self.assertTrue(
            QuestionGrade.objects.filter(
                submission=self.submission, question=self.question,
            ).exists()
        )

    def test_grade_submission_sends_notification(self):
        Notification.objects.all().delete()
        self.faculty_client.post(
            reverse('grade_submission', args=[self.submission.id]),
            data=json.dumps({
                'question_grades': [{'question_id': self.question.id, 'marks': 18}],
                'sub_question_grades': [], 'feedback': '',
            }),
            content_type='application/json',
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='grade_released',
            ).exists()
        )


class FacultyAnalyticsEscarViewTests(BaseTestCase):
    def test_analytics_200(self):
        response = self.faculty_client.get(reverse('faculty_analytics'))
        self.assertEqual(response.status_code, 200)

    def test_analytics_with_course(self):
        response = self.faculty_client.get(
            reverse('faculty_analytics') + f'?course={self.course.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_course'], self.course)

    def test_escar_200(self):
        response = self.faculty_client.get(reverse('faculty_escar'))
        self.assertEqual(response.status_code, 200)

    def test_escar_with_course(self):
        response = self.faculty_client.get(
            reverse('faculty_escar') + f'?course={self.course.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_course'], self.course)

    def test_save_escar_plan_clo(self):
        response = self.faculty_client.post(
            reverse('save_escar_plan'),
            data=json.dumps({
                'course_id': self.course.id,
                'type': 'clo',
                'id': self.clo.id,
                'action_plan': 'Improve lab sessions',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        plan = CLOActionPlan.objects.get(course=self.course, clo=self.clo)
        self.assertEqual(plan.action_plan, 'Improve lab sessions')

    def test_save_escar_plan_plo(self):
        response = self.faculty_client.post(
            reverse('save_escar_plan'),
            data=json.dumps({
                'course_id': self.course.id,
                'type': 'plo',
                'id': self.plo.id,
                'action_plan': 'Strengthen problem solving',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        plan = PLOActionPlan.objects.get(course=self.course, plo=self.plo)
        self.assertEqual(plan.action_plan, 'Strengthen problem solving')

    def test_save_escar_plan_invalid_type(self):
        response = self.faculty_client.post(
            reverse('save_escar_plan'),
            data=json.dumps({
                'course_id': self.course.id,
                'type': 'unknown', 'id': 1, 'action_plan': 'X',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class FacultyAnnouncementsViewTests(BaseTestCase):
    def test_announcements_list_200(self):
        response = self.faculty_client.get(reverse('faculty_announcements'))
        self.assertEqual(response.status_code, 200)

    def test_create_announcement_success(self):
        response = self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'No class on Monday',
                'content': 'Class suspended.',
                'priority': 'high',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Announcement.objects.filter(title='No class on Monday').exists()
        )

    def test_create_announcement_sends_notification_to_enrolled(self):
        Enrollment.objects.get_or_create(student=self.student, course=self.course)
        Notification.objects.all().delete()
        self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Ann Notif Test',
                'content': 'See class schedule.',
                'priority': 'medium',
            }),
            content_type='application/json',
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notif_type='announcement',
            ).exists()
        )

    def test_delete_announcement_success(self):
        ann = Announcement.objects.create(
            course=self.course, title='Delete Me',
            content='bye', priority='low', created_by=self.faculty,
        )
        response = self.faculty_client.post(
            reverse('delete_announcement', args=[ann.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(Announcement.objects.filter(id=ann.id).exists())


class FacultyMaterialsViewTests(BaseTestCase):
    def test_materials_list_200(self):
        response = self.faculty_client.get(reverse('faculty_materials'))
        self.assertEqual(response.status_code, 200)

    def test_materials_with_course_200(self):
        response = self.faculty_client.get(
            reverse('faculty_materials') + f'?course={self.course.id}'
        )
        self.assertEqual(response.status_code, 200)

    def test_upload_material_file(self):
        f = SimpleUploadedFile('notes.txt', b'content', content_type='text/plain')
        response = self.faculty_client.post(
            reverse('upload_material'),
            {
                'course_id': self.course.id,
                'title': 'Week 1 Notes',
                'material_type': 'lecture_note',
                'file': f,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(StudyMaterial.objects.filter(title='Week 1 Notes').exists())

    def test_upload_material_video_url(self):
        response = self.faculty_client.post(
            reverse('upload_material'),
            {
                'course_id': self.course.id,
                'title': 'Lecture Video',
                'material_type': 'video',
                'video_url': 'https://www.youtube.com/watch?v=test123',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_upload_material_no_title_returns_error(self):
        f = SimpleUploadedFile('f.txt', b'x')
        response = self.faculty_client.post(
            reverse('upload_material'),
            {'course_id': self.course.id, 'title': '', 'material_type': 'lecture_note', 'file': f},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_material_success(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='To Delete',
            material_type='lecture_note', uploaded_by=self.faculty,
        )
        response = self.faculty_client.post(
            reverse('delete_material', args=[mat.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(StudyMaterial.objects.filter(id=mat.id).exists())

    def test_toggle_material_visibility(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Toggleable',
            material_type='lecture_note', uploaded_by=self.faculty,
            is_visible=True,
        )
        response = self.faculty_client.post(
            reverse('toggle_material_visibility', args=[mat.id])
        )
        self.assertEqual(response.status_code, 200)
        mat.refresh_from_db()
        self.assertFalse(mat.is_visible)
        # Toggle again
        self.faculty_client.post(reverse('toggle_material_visibility', args=[mat.id]))
        mat.refresh_from_db()
        self.assertTrue(mat.is_visible)


class FacultyQuestionBankViewTests(BaseTestCase):
    def test_question_bank_200(self):
        response = self.faculty_client.get(reverse('faculty_question_bank'))
        self.assertEqual(response.status_code, 200)

    def test_create_past_paper_success(self):
        response = self.faculty_client.post(
            reverse('create_past_paper'),
            data=json.dumps({
                'title': 'Final Exam 2024',
                'course_code': 'CS101',
                'course_name': 'Intro to CS',
                'semester': 'Fall 2024',
                'exam_type': 'final',
                'total_marks': 60,
                'is_public': True,
                'questions': [
                    {'text': 'Explain OOP', 'marks': 10, 'difficulty': 'medium'},
                ],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(PastPaper.objects.filter(title='Final Exam 2024').exists())

    def test_create_past_paper_creates_questions(self):
        self.faculty_client.post(
            reverse('create_past_paper'),
            data=json.dumps({
                'title': 'Paper With Qs',
                'course_code': 'CS101', 'course_name': 'Intro',
                'semester': 'Fall 2024', 'exam_type': 'mid',
                'questions': [
                    {'text': 'Q1', 'marks': 5},
                    {'text': 'Q2', 'marks': 10},
                ],
            }),
            content_type='application/json',
        )
        paper = PastPaper.objects.get(title='Paper With Qs')
        self.assertEqual(paper.questions.count(), 2)

    def test_delete_past_paper_success(self):
        paper = PastPaper.objects.create(
            title='Del Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='mid', uploaded_by=self.faculty,
        )
        response = self.faculty_client.post(
            reverse('delete_past_paper', args=[paper.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(PastPaper.objects.filter(id=paper.id).exists())

    def test_toggle_paper_visibility(self):
        paper = PastPaper.objects.create(
            title='Toggle Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='mid',
            uploaded_by=self.faculty, is_public=False,
        )
        response = self.faculty_client.post(
            reverse('toggle_paper_visibility', args=[paper.id])
        )
        self.assertEqual(response.status_code, 200)
        paper.refresh_from_db()
        self.assertTrue(paper.is_public)
        self.faculty_client.post(reverse('toggle_paper_visibility', args=[paper.id]))
        paper.refresh_from_db()
        self.assertFalse(paper.is_public)

    def test_toggle_hint_visibility(self):
        paper = PastPaper.objects.create(
            title='Hint Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='quiz', uploaded_by=self.faculty,
        )
        q = PastPaperQuestion.objects.create(
            paper=paper, order=1, text='Q with hint', marks=5,
            answer_hint='The answer is 42', show_hint=False,
        )
        response = self.faculty_client.post(
            reverse('toggle_hint_visibility', args=[q.id])
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertTrue(q.show_hint)


class FacultyEnrolledStudentsViewTests(BaseTestCase):
    def test_enrolled_students_200(self):
        response = self.faculty_client.get(reverse('faculty_enrolled_students'))
        self.assertEqual(response.status_code, 200)

    def test_enrolled_students_search(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.faculty_client.get(
            reverse('faculty_enrolled_students') + '?q=Alice'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)

    def test_enrolled_students_search_no_match(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.faculty_client.get(
            reverse('faculty_enrolled_students') + '?q=Zzz_no_match'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)

    def test_enrolled_students_course_filter(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.faculty_client.get(
            reverse('faculty_enrolled_students') + f'?course={self.course.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)


class FacultyMarksSheetViewTests(BaseTestCase):
    def test_marks_sheet_200(self):
        response = self.faculty_client.get(reverse('faculty_marks_sheet'))
        self.assertEqual(response.status_code, 200)

    def test_update_question_grade_creates_grade(self):
        assessment = Assessment.objects.create(
            course=self.course, title='MS Test', assessment_type='quiz', total_marks=10,
        )
        question = Question.objects.create(
            assessment=assessment, order=1, text='Q?', max_marks=10,
        )
        submission = Submission.objects.create(
            student=self.student, assessment=assessment,
        )
        response = self.faculty_client.post(
            reverse('update_question_grade'),
            data=json.dumps({
                'student_id': self.student.id,
                'question_id': question.id,
                'marks': 8,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))
        self.assertTrue(
            QuestionGrade.objects.filter(submission=submission, question=question).exists()
        )

    def test_update_question_grade_invalid_question(self):
        response = self.faculty_client.post(
            reverse('update_question_grade'),
            data=json.dumps({
                'student_id': self.student.id,
                'question_id': 99999,
                'marks': 5,
            }),
            content_type='application/json',
        )
        # get_object_or_404 raises 404 for non-existent question
        self.assertEqual(response.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 6. STUDENT VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────
class StudentDashboardViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.course)

    def test_dashboard_200(self):
        response = self.student_client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'student/dashboard.html')

    def test_dashboard_context_has_courses(self):
        response = self.student_client.get(reverse('student_dashboard'))
        self.assertIn('courses', response.context)
        self.assertIn(self.course, response.context['courses'])

    def test_dashboard_context_counts(self):
        response = self.student_client.get(reverse('student_dashboard'))
        for key in ('pending_count', 'avg_grade', 'submissions_count'):
            self.assertIn(key, response.context)


class StudentCoursesViewTests(BaseTestCase):
    def test_courses_200(self):
        response = self.student_client.get(reverse('student_courses'))
        self.assertEqual(response.status_code, 200)

    def test_courses_shows_enrolled(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.student_client.get(reverse('student_courses'))
        self.assertIn(self.course, response.context['courses'])

    def test_courses_shows_unenrolled_in_all_courses(self):
        response = self.student_client.get(reverse('student_courses'))
        all_course_ids = [c.id for c in response.context['all_courses']]
        self.assertIn(self.course.id, all_course_ids)

    def test_enroll_course_success(self):
        response = self.student_client.post(
            reverse('enroll_course', args=[self.course.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_enroll_course_idempotent(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.student_client.post(
            reverse('enroll_course', args=[self.course.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, course=self.course).count(), 1
        )


class StudentSubmissionsViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assessment = Assessment.objects.create(
            course=self.course, title='HW1',
            assessment_type='assignment', status='published', total_marks=20,
        )

    def test_submissions_200(self):
        response = self.student_client.get(reverse('student_submissions'))
        self.assertEqual(response.status_code, 200)

    def test_submissions_context_has_todo(self):
        response = self.student_client.get(reverse('student_submissions'))
        self.assertIn('todo_assessments', response.context)

    def test_submit_assessment_success(self):
        response = self.student_client.post(
            reverse('submit_assessment', args=[self.assessment.id]),
            data=json.dumps({'content': 'My solution here'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Submission.objects.filter(
                student=self.student, assessment=self.assessment,
            ).exists()
        )

    def test_submit_assessment_already_submitted(self):
        Submission.objects.create(student=self.student, assessment=self.assessment)
        response = self.student_client.post(
            reverse('submit_assessment', args=[self.assessment.id]),
            data=json.dumps({'content': 'Second attempt'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Already', response.json()['error'])

    def test_submit_assessment_not_enrolled(self):
        other_course = Course.objects.create(
            code='CS999', name='Other', faculty=self.faculty, semester='Fall 2025',
        )
        other_assessment = Assessment.objects.create(
            course=other_course, title='Other HW', assessment_type='assignment', status='published',
        )
        response = self.student_client.post(
            reverse('submit_assessment', args=[other_assessment.id]),
            data=json.dumps({'content': 'Hi'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn('Not enrolled', response.json()['error'])


class StudentAssignmentsViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.course)
        self.assessment = Assessment.objects.create(
            course=self.course, title='Assignment A',
            assessment_type='assignment', status='published', total_marks=30,
            due_date=(datetime.date.today() + datetime.timedelta(days=7)),
        )

    def test_assignments_200(self):
        response = self.student_client.get(reverse('student_assignments'))
        self.assertEqual(response.status_code, 200)

    def test_assignments_context_has_assignments(self):
        response = self.student_client.get(reverse('student_assignments'))
        assessments = [a for a, _, _ in response.context['assignments_with_status']]
        self.assertIn(self.assessment, assessments)

    def test_submit_assignment_success(self):
        response = self.student_client.post(
            reverse('submit_assignment', args=[self.assessment.id]),
            {'content': 'Here is my assignment answer.'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Submission.objects.filter(
                student=self.student, assessment=self.assessment,
            ).exists()
        )

    def test_submit_assignment_not_enrolled(self):
        other_course = Course.objects.create(
            code='OTHER', name='Other Course', faculty=self.faculty, semester='Fall 2025',
        )
        other_assessment = Assessment.objects.create(
            course=other_course, title='Other A',
            assessment_type='assignment', status='published',
            due_date=(datetime.date.today() + datetime.timedelta(days=3)),
        )
        response = self.student_client.post(
            reverse('submit_assignment', args=[other_assessment.id]),
            {'content': 'Trying without enrollment'},
        )
        self.assertEqual(response.status_code, 403)

    def test_submit_assignment_already_submitted(self):
        Submission.objects.create(student=self.student, assessment=self.assessment)
        response = self.student_client.post(
            reverse('submit_assignment', args=[self.assessment.id]),
            {'content': 'Second try'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('already submitted', response.json()['error'])

    def test_submit_assignment_empty_content_and_no_file(self):
        response = self.student_client.post(
            reverse('submit_assignment', args=[self.assessment.id]),
            {'content': ''},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('answer', response.json()['error'])

    def test_submit_assignment_with_file(self):
        f = SimpleUploadedFile('answer.txt', b'My solution', content_type='text/plain')
        response = self.student_client.post(
            reverse('submit_assignment', args=[self.assessment.id]),
            {'submitted_file': f},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])


class StudentNotificationsViewTests(BaseTestCase):
    def test_notifications_200(self):
        response = self.student_client.get(reverse('student_notifications'))
        self.assertEqual(response.status_code, 200)

    def test_notifications_shows_notifications(self):
        Notification.objects.create(
            recipient=self.student, notif_type='new_assignment',
            title='Test Notif', message='msg',
        )
        response = self.student_client.get(reverse('student_notifications'))
        self.assertContains(response, 'Test Notif')

    def test_notifications_page_marks_all_read(self):
        Notification.objects.create(
            recipient=self.student, notif_type='grade_released',
            title='Grade', message='msg', is_read=False,
        )
        self.student_client.get(reverse('student_notifications'))
        self.assertEqual(
            Notification.objects.filter(recipient=self.student, is_read=False).count(), 0
        )

    def test_notifications_unread_count_in_context(self):
        Notification.objects.create(
            recipient=self.student, notif_type='new_material',
            title='N', message='m', is_read=False,
        )
        response = self.student_client.get(reverse('student_notifications'))
        self.assertIn('unread_count', response.context)

    def test_get_unread_count_json(self):
        Notification.objects.create(
            recipient=self.student, notif_type='new_assignment',
            title='U', message='m', is_read=False,
        )
        response = self.student_client.get(reverse('get_unread_count'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.json())
        self.assertGreaterEqual(response.json()['count'], 1)

    def test_mark_all_read_clears_unread(self):
        for i in range(3):
            Notification.objects.create(
                recipient=self.student, notif_type='new_assignment',
                title=f'N{i}', message='m', is_read=False,
            )
        response = self.student_client.post(reverse('mark_all_read'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(recipient=self.student, is_read=False).count(), 0
        )


class StudentCLOResultsViewTests(BaseTestCase):
    def test_clo_results_200(self):
        response = self.student_client.get(reverse('student_clo_results'))
        self.assertEqual(response.status_code, 200)

    def test_clo_results_shows_enrolled_courses(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        response = self.student_client.get(reverse('student_clo_results'))
        courses_in_results = [r['course'] for r in response.context['results']]
        self.assertIn(self.course, courses_in_results)

    def test_clo_results_grade_logic(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        assessment = Assessment.objects.create(
            course=self.course, title='Graded A', assessment_type='quiz',
            total_marks=100, status='published',
        )
        Submission.objects.create(
            student=self.student, assessment=assessment,
            total_score=85, status='graded',
        )
        response = self.student_client.get(reverse('student_clo_results'))
        result = next(r for r in response.context['results'] if r['course'] == self.course)
        self.assertGreaterEqual(result['avg_pct'], 80)


class StudentMaterialsViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.course)

    def test_materials_200(self):
        response = self.student_client.get(reverse('student_materials'))
        self.assertEqual(response.status_code, 200)

    def test_materials_shows_visible_only(self):
        mat_vis = StudyMaterial.objects.create(
            course=self.course, title='Visible Material',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=True,
        )
        mat_hidden = StudyMaterial.objects.create(
            course=self.course, title='Hidden Material',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=False,
        )
        response = self.student_client.get(
            reverse('student_materials') + f'?course={self.course.id}'
        )
        self.assertContains(response, 'Visible Material')
        self.assertNotContains(response, 'Hidden Material')

    def test_materials_unenrolled_redirects(self):
        other_course = Course.objects.create(
            code='OTH', name='Other', faculty=self.faculty, semester='X',
        )
        response = self.student_client.get(
            reverse('student_materials') + f'?course={other_course.id}'
        )
        self.assertRedirects(response, reverse('student_materials'))


class StudentQuestionBankViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.course)

    def test_question_bank_200(self):
        response = self.student_client.get(reverse('student_question_bank'))
        self.assertEqual(response.status_code, 200)

    def test_qbank_course_200(self):
        response = self.student_client.get(
            reverse('student_qbank_course', args=[self.course.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_qbank_type_200(self):
        response = self.student_client.get(
            reverse('student_qbank_type', args=[self.course.id, 'assignment'])
        )
        self.assertEqual(response.status_code, 200)

    def test_view_past_paper_public(self):
        paper = PastPaper.objects.create(
            title='Public Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='mid',
            uploaded_by=self.faculty, is_public=True,
        )
        response = self.student_client.get(
            reverse('student_view_paper', args=[paper.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_view_past_paper_restricted_enrolled_course(self):
        paper = PastPaper.objects.create(
            title='Restricted Paper', course_code='CS101', course_name='Intro',
            semester='Fall 2024', exam_type='mid',
            uploaded_by=self.faculty, is_public=False,
        )
        paper.allowed_courses.add(self.course)
        response = self.student_client.get(
            reverse('student_view_paper', args=[paper.id])
        )
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 7. PERMISSION / ACCESS CONTROL TESTS
# ─────────────────────────────────────────────────────────────────────────────
class PermissionTests(BaseTestCase):
    def test_unauthenticated_faculty_dashboard_redirects(self):
        c = Client()
        response = c.get(reverse('faculty_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('signin', response.url)

    def test_unauthenticated_student_dashboard_redirects(self):
        c = Client()
        response = c.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('signin', response.url)

    def test_student_accessing_faculty_dashboard_redirected(self):
        """Student is redirected away from faculty views."""
        response = self.student_client.get(reverse('faculty_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('student_dashboard'))

    def test_faculty_accessing_student_dashboard_redirected(self):
        """Faculty is redirected away from student views."""
        response = self.faculty_client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('faculty_dashboard'))

    def test_student_cannot_access_faculty_courses(self):
        response = self.student_client.get(reverse('faculty_courses'))
        self.assertEqual(response.status_code, 302)

    def test_faculty_cannot_access_student_submissions(self):
        response = self.faculty_client.get(reverse('student_submissions'))
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_add_course(self):
        response = self.student_client.post(
            reverse('add_course'),
            data=json.dumps({'code': 'X', 'name': 'Y'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_faculty_cannot_enroll_in_course(self):
        response = self.faculty_client.post(
            reverse('enroll_course', args=[self.course.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_add_plo_redirects(self):
        c = Client()
        response = c.post(
            reverse('add_plo'),
            data=json.dumps({'description': 'x'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_create_assignment_redirects(self):
        c = Client()
        response = c.post(
            reverse('create_assignment'),
            data=json.dumps({'title': 'x', 'course_id': 1}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_faculty_cannot_submit_assessment(self):
        assessment = Assessment.objects.create(
            course=self.course, title='Test', assessment_type='quiz', status='published',
        )
        response = self.faculty_client.post(
            reverse('submit_assessment', args=[assessment.id]),
            data=json.dumps({'content': 'answer'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_grade_submission(self):
        assessment = Assessment.objects.create(
            course=self.course, title='Q', assessment_type='quiz', status='published',
        )
        sub = Submission.objects.create(student=self.student, assessment=assessment)
        response = self.student_client.post(
            reverse('grade_submission', args=[sub.id]),
            data=json.dumps({'question_grades': [], 'sub_question_grades': [], 'feedback': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_faculty_owns_course_only(self):
        """Faculty cannot add CLO to another faculty's course."""
        other_faculty = User.objects.create_user(
            username='other.f', email='other.f@uap-bd.edu',
            password='pass12345', role='faculty',
        )
        other_course = Course.objects.create(
            code='OTH', name='Other', faculty=other_faculty, semester='X',
        )
        response = self.faculty_client.post(
            reverse('add_clo', args=[other_course.id]),
            data=json.dumps({'description': 'Hack', 'bloom_level': 'Remember (L1)'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
