# test_sections_dao.py
# Tests for: Section model, DAO portal views, section-based content filtering,
# faculty section assignment features, and announcement section targeting.

import json
import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import IntegrityError

from evalify_app.models import (
    Course, CLO, PLO, Assessment, Question,
    Enrollment, Submission, StudyMaterial, Announcement, Notification,
    Section,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared base
# ─────────────────────────────────────────────────────────────────────────────
class SectionBaseTestCase(TestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            username='sec_faculty', email='sec.faculty@uap-bd.edu',
            password='pass12345', role='faculty', full_name='Sec Faculty',
        )
        self.student1 = User.objects.create_user(
            username='20230001', email='20230001@uap-bd.edu',
            password='pass12345', role='student', full_name='Student One',
        )
        self.student2 = User.objects.create_user(
            username='20230002', email='20230002@uap-bd.edu',
            password='pass12345', role='student', full_name='Student Two',
        )
        self.dao = User.objects.create_user(
            username='dao_test', email='dao.test@uap-bd.edu',
            password='pass12345', role='dao', full_name='DAO User',
        )
        self.course = Course.objects.create(
            code='CS200', name='Test Course',
            semester='Fall 2025', credit_hours=3,
        )
        self.course.faculty.add(self.faculty)
        self.faculty_client = Client()
        self.faculty_client.login(username='sec_faculty', password='pass12345')
        self.student1_client = Client()
        self.student1_client.login(username='20230001', password='pass12345')
        self.dao_client = Client()
        self.dao_client.login(username='dao_test', password='pass12345')


# ─────────────────────────────────────────────────────────────────────────────
# 1. SECTION MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────
class SectionModelTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        self.section = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )

    def test_str(self):
        self.assertEqual(str(self.section), 'CS200 | Fall 2025 | Sec A')

    def test_code_auto_generated_on_create(self):
        self.assertTrue(bool(self.section.code))

    def test_code_contains_course_code(self):
        self.assertIn('CS200', self.section.code)

    def test_code_contains_section_name(self):
        self.assertIn('A', self.section.code.upper())

    def test_code_contains_batch_shortcode(self):
        # 'Fall 2025' → first letter of 'Fall' + last 2 of '2025' → 'F25'
        self.assertIn('F25', self.section.code)

    def test_different_section_names_get_different_codes(self):
        sec_b = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )
        self.assertNotEqual(self.section.code, sec_b.code)

    def test_students_m2m_add(self):
        self.section.students.add(self.student1)
        self.assertIn(self.student1, self.section.students.all())

    def test_students_m2m_remove(self):
        self.section.students.add(self.student1)
        self.section.students.remove(self.student1)
        self.assertNotIn(self.student1, self.section.students.all())

    def test_faculty_m2m_add(self):
        self.section.faculty.add(self.faculty)
        self.assertIn(self.faculty, self.section.faculty.all())

    def test_unique_together_raises_on_duplicate(self):
        with self.assertRaises(Exception):
            Section.objects.create(
                course=self.course, name='A', batch='Fall 2025',
            )

    def test_cascade_delete_when_course_deleted(self):
        sec_id = self.section.id
        self.course.delete()
        self.assertFalse(Section.objects.filter(id=sec_id).exists())

    def test_code_not_blank_after_save(self):
        self.assertNotEqual(self.section.code, '')

    def test_section_ordering(self):
        sec_b = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )
        sections = list(Section.objects.filter(course=self.course))
        self.assertEqual(sections[0].name, 'A')
        self.assertEqual(sections[1].name, 'B')

    def test_multiple_students_in_section(self):
        self.section.students.add(self.student1, self.student2)
        self.assertEqual(self.section.students.count(), 2)

    def test_multiple_faculty_in_section(self):
        faculty2 = User.objects.create_user(
            username='fac2', email='fac2@uap-bd.edu',
            password='x', role='faculty',
        )
        self.section.faculty.add(self.faculty, faculty2)
        self.assertEqual(self.section.faculty.count(), 2)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DAO PORTAL PERMISSION TESTS
# ─────────────────────────────────────────────────────────────────────────────
class DAOPortalPermissionTests(SectionBaseTestCase):
    def test_faculty_cannot_access_dao_dashboard(self):
        response = self.faculty_client.get(reverse('dao_dashboard'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_student_cannot_access_dao_dashboard(self):
        response = self.student1_client.get(reverse('dao_dashboard'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_unauthenticated_redirected_from_dao_dashboard(self):
        c = Client()
        response = c.get(reverse('dao_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('signin', response.url)

    def test_dao_user_can_access_dashboard(self):
        response = self.dao_client.get(reverse('dao_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_faculty_cannot_access_dao_sections(self):
        response = self.faculty_client.get(reverse('dao_sections'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_student_cannot_access_dao_users(self):
        response = self.student1_client.get(reverse('dao_users'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_unauthenticated_redirected_from_dao_sections(self):
        c = Client()
        response = c.get(reverse('dao_sections'))
        self.assertIn('signin', c.get(reverse('dao_sections')).url)


# ─────────────────────────────────────────────────────────────────────────────
# 3. DAO PORTAL VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────
class DAODashboardTests(SectionBaseTestCase):
    def test_dashboard_200(self):
        response = self.dao_client.get(reverse('dao_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dao_portal/dashboard.html')

    def test_dashboard_context_has_counts(self):
        response = self.dao_client.get(reverse('dao_dashboard'))
        for key in ('total_faculty', 'total_students', 'total_courses'):
            self.assertIn(key, response.context)

    def test_dashboard_counts_reflect_db(self):
        response = self.dao_client.get(reverse('dao_dashboard'))
        self.assertGreaterEqual(response.context['total_faculty'], 1)
        self.assertGreaterEqual(response.context['total_students'], 2)
        self.assertGreaterEqual(response.context['total_courses'], 1)


class DAOUsersViewTests(SectionBaseTestCase):
    def test_users_list_200(self):
        response = self.dao_client.get(reverse('dao_users'))
        self.assertEqual(response.status_code, 200)

    def test_users_list_shows_users(self):
        response = self.dao_client.get(reverse('dao_users'))
        self.assertContains(response, self.faculty.full_name)

    def test_create_user_success(self):
        response = self.dao_client.post(reverse('dao_create_user'), {
            'full_name': 'New Faculty',
            'email': 'new.faculty@uap-bd.edu',
            'password': 'testpass123',
            'role': 'faculty',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='new.faculty@uap-bd.edu').exists())

    def test_toggle_user_changes_active_state(self):
        target = User.objects.create_user(
            username='toggle_user', email='toggle@uap-bd.edu',
            password='pass', role='faculty', is_active=True,
        )
        self.dao_client.post(reverse('dao_toggle_user', args=[target.id]))
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_delete_user_removes_user(self):
        target = User.objects.create_user(
            username='del_user', email='del.user@uap-bd.edu',
            password='pass', role='faculty',
        )
        self.dao_client.post(reverse('dao_delete_user', args=[target.id]))
        self.assertFalse(User.objects.filter(id=target.id).exists())


class DAOCoursesViewTests(SectionBaseTestCase):
    def test_courses_list_200(self):
        response = self.dao_client.get(reverse('dao_courses'))
        self.assertEqual(response.status_code, 200)

    def test_courses_list_shows_courses(self):
        response = self.dao_client.get(reverse('dao_courses'))
        self.assertContains(response, self.course.code)

    def test_create_course_success(self):
        response = self.dao_client.post(reverse('dao_create_course'), {
            'code': 'NEW301',
            'name': 'New Course',
            'semester': 'Spring 2026',
            'credit_hours': 3,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Course.objects.filter(code='NEW301').exists())

    def test_assign_faculty_to_course(self):
        response = self.dao_client.post(
            reverse('dao_assign_faculty', args=[self.course.id]),
            data=json.dumps({'faculty_id': self.faculty.id}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 302])


class DAOSectionsViewTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        self.section = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )

    def test_sections_list_200(self):
        response = self.dao_client.get(reverse('dao_sections'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dao_portal/sections.html')

    def test_sections_list_contains_section_code(self):
        response = self.dao_client.get(reverse('dao_sections'))
        self.assertContains(response, self.section.code)

    def test_section_detail_200(self):
        response = self.dao_client.get(
            reverse('dao_section_detail', args=[self.section.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dao_portal/section_detail.html')

    def test_section_detail_context_has_faculty_list(self):
        response = self.dao_client.get(
            reverse('dao_section_detail', args=[self.section.id])
        )
        self.assertIn('faculty_list', response.context)

    def test_section_detail_context_has_students(self):
        self.section.students.add(self.student1)
        response = self.dao_client.get(
            reverse('dao_section_detail', args=[self.section.id])
        )
        self.assertIn('students', response.context)
        self.assertIn(self.student1, response.context['students'])

    def test_create_section_success(self):
        response = self.dao_client.post(reverse('dao_create_section'), {
            'course_id': self.course.id,
            'name': 'B',
            'batch': 'Fall 2025',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Section.objects.filter(course=self.course, name='B', batch='Fall 2025').exists()
        )

    def test_create_section_auto_generates_code(self):
        self.dao_client.post(reverse('dao_create_section'), {
            'course_id': self.course.id,
            'name': 'C',
            'batch': 'Fall 2025',
        })
        sec = Section.objects.get(course=self.course, name='C', batch='Fall 2025')
        self.assertTrue(bool(sec.code))

    def test_assign_faculty_to_section(self):
        self.dao_client.post(
            reverse('dao_section_assign_faculty', args=[self.section.id]),
            {'faculty_ids': [self.faculty.id]},
        )
        self.assertIn(self.faculty, self.section.faculty.all())

    def test_clear_faculty_from_section(self):
        self.section.faculty.add(self.faculty)
        self.dao_client.post(
            reverse('dao_section_assign_faculty', args=[self.section.id]),
            {},  # no faculty_ids → clears
        )
        self.assertEqual(self.section.faculty.count(), 0)

    # ── Range student assignment ──
    def test_assign_students_by_range_adds_both(self):
        self.dao_client.post(
            reverse('dao_section_assign_students', args=[self.section.id]),
            {'start_reg_id': '20230001', 'end_reg_id': '20230002'},
        )
        self.assertIn(self.student1, self.section.students.all())
        self.assertIn(self.student2, self.section.students.all())

    def test_assign_students_range_empty_ids_shows_error_no_students_added(self):
        self.dao_client.post(
            reverse('dao_section_assign_students', args=[self.section.id]),
            {'start_reg_id': '', 'end_reg_id': ''},
        )
        self.assertEqual(self.section.students.count(), 0)

    def test_assign_students_range_no_matching_ids_adds_none(self):
        self.dao_client.post(
            reverse('dao_section_assign_students', args=[self.section.id]),
            {'start_reg_id': 'ZZZZZ001', 'end_reg_id': 'ZZZZZ999'},
        )
        self.assertEqual(self.section.students.count(), 0)

    # ── Single student addition ──
    def test_add_single_student_success(self):
        self.dao_client.post(
            reverse('dao_section_add_single_student', args=[self.section.id]),
            {'reg_id': '20230001'},
        )
        self.assertIn(self.student1, self.section.students.all())

    def test_add_single_student_not_found_adds_nobody(self):
        self.dao_client.post(
            reverse('dao_section_add_single_student', args=[self.section.id]),
            {'reg_id': 'NONEXISTENT999'},
        )
        self.assertEqual(self.section.students.count(), 0)

    def test_add_single_student_already_in_section_no_duplicate(self):
        self.section.students.add(self.student1)
        self.dao_client.post(
            reverse('dao_section_add_single_student', args=[self.section.id]),
            {'reg_id': '20230001'},
        )
        self.assertEqual(
            self.section.students.filter(id=self.student1.id).count(), 1
        )

    def test_add_single_student_empty_reg_id_adds_nobody(self):
        self.dao_client.post(
            reverse('dao_section_add_single_student', args=[self.section.id]),
            {'reg_id': ''},
        )
        self.assertEqual(self.section.students.count(), 0)

    def test_add_single_student_redirects_to_section_detail(self):
        response = self.dao_client.post(
            reverse('dao_section_add_single_student', args=[self.section.id]),
            {'reg_id': '20230001'},
        )
        self.assertRedirects(
            response,
            reverse('dao_section_detail', args=[self.section.id]),
            fetch_redirect_response=False,
        )

    # ── Remove student ──
    def test_remove_student_from_section(self):
        self.section.students.add(self.student1)
        self.dao_client.post(
            reverse('dao_section_remove_student', args=[self.section.id, self.student1.id])
        )
        self.assertNotIn(self.student1, self.section.students.all())

    def test_remove_student_redirects_to_section_detail(self):
        self.section.students.add(self.student1)
        response = self.dao_client.post(
            reverse('dao_section_remove_student', args=[self.section.id, self.student1.id])
        )
        self.assertRedirects(
            response,
            reverse('dao_section_detail', args=[self.section.id]),
            fetch_redirect_response=False,
        )

    # ── Delete section ──
    def test_delete_section_removes_it(self):
        sec_id = self.section.id
        self.dao_client.post(reverse('dao_delete_section', args=[self.section.id]))
        self.assertFalse(Section.objects.filter(id=sec_id).exists())

    def test_delete_section_redirects_to_sections_list(self):
        response = self.dao_client.post(
            reverse('dao_delete_section', args=[self.section.id])
        )
        self.assertRedirects(
            response, reverse('dao_sections'), fetch_redirect_response=False
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. SECTION-BASED CONTENT FILTERING TESTS
# ─────────────────────────────────────────────────────────────────────────────
class SectionContentFilterTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student1, course=self.course)
        Enrollment.objects.create(student=self.student2, course=self.course)
        self.section_a = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )
        self.section_b = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )
        self.section_a.students.add(self.student1)
        self.section_b.students.add(self.student2)

    # ── Assessments ──
    def test_student_sees_course_wide_assessment(self):
        """Assessment with no sections set is visible to all enrolled students."""
        assessment = Assessment.objects.create(
            course=self.course, title='Course Wide HW',
            assessment_type='assignment', status='published', total_marks=10,
        )
        response = self.student1_client.get(
            reverse('student_course_assignments', args=[self.course.id])
        )
        assessments = [a for a, _, _ in response.context['assignments_with_status']]
        self.assertIn(assessment, assessments)

    def test_student_sees_own_section_assessment(self):
        assessment = Assessment.objects.create(
            course=self.course, title='Section A HW',
            assessment_type='assignment', status='published', total_marks=10,
        )
        assessment.sections.add(self.section_a)
        response = self.student1_client.get(
            reverse('student_course_assignments', args=[self.course.id])
        )
        assessments = [a for a, _, _ in response.context['assignments_with_status']]
        self.assertIn(assessment, assessments)

    def test_student_cannot_see_other_section_assessment(self):
        assessment = Assessment.objects.create(
            course=self.course, title='Section B Only HW',
            assessment_type='assignment', status='published', total_marks=10,
        )
        assessment.sections.add(self.section_b)
        # student1 is in section_a, not section_b
        response = self.student1_client.get(
            reverse('student_course_assignments', args=[self.course.id])
        )
        assessments = [a for a, _, _ in response.context['assignments_with_status']]
        self.assertNotIn(assessment, assessments)

    def test_student_in_multiple_sections_sees_both(self):
        self.section_b.students.add(self.student1)
        hw_a = Assessment.objects.create(
            course=self.course, title='Sec A', assessment_type='assignment',
            status='published', total_marks=5,
        )
        hw_a.sections.add(self.section_a)
        hw_b = Assessment.objects.create(
            course=self.course, title='Sec B', assessment_type='assignment',
            status='published', total_marks=5,
        )
        hw_b.sections.add(self.section_b)
        response = self.student1_client.get(
            reverse('student_course_assignments', args=[self.course.id])
        )
        assessments = [a for a, _, _ in response.context['assignments_with_status']]
        self.assertIn(hw_a, assessments)
        self.assertIn(hw_b, assessments)

    # ── Materials ──
    def test_student_sees_course_wide_material(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Course Wide Notes',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=True,
        )
        response = self.student1_client.get(
            reverse('student_materials') + f'?course={self.course.id}'
        )
        self.assertContains(response, 'Course Wide Notes')

    def test_student_sees_own_section_material(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Section A Notes',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=True,
        )
        mat.sections.add(self.section_a)
        response = self.student1_client.get(
            reverse('student_materials') + f'?course={self.course.id}'
        )
        self.assertContains(response, 'Section A Notes')

    def test_student_cannot_see_other_section_material(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Section B Notes',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=True,
        )
        mat.sections.add(self.section_b)
        response = self.student1_client.get(
            reverse('student_materials') + f'?course={self.course.id}'
        )
        self.assertNotContains(response, 'Section B Notes')

    def test_hidden_material_not_shown_regardless_of_section(self):
        mat = StudyMaterial.objects.create(
            course=self.course, title='Hidden Section A',
            material_type='lecture_note', uploaded_by=self.faculty, is_visible=False,
        )
        mat.sections.add(self.section_a)
        response = self.student1_client.get(
            reverse('student_materials') + f'?course={self.course.id}'
        )
        self.assertNotContains(response, 'Hidden Section A')

    # ── Announcements (dashboard) ──
    def test_student_sees_course_wide_announcement_on_dashboard(self):
        Announcement.objects.create(
            course=self.course, title='General Notice',
            content='For everyone', priority='medium', created_by=self.faculty,
        )
        response = self.student1_client.get(reverse('student_dashboard'))
        self.assertContains(response, 'General Notice')

    def test_student_sees_own_section_announcement_on_dashboard(self):
        ann = Announcement.objects.create(
            course=self.course, title='Section A Notice',
            content='Section A only', priority='low', created_by=self.faculty,
        )
        ann.sections.add(self.section_a)
        response = self.student1_client.get(reverse('student_dashboard'))
        self.assertContains(response, 'Section A Notice')

    def test_student_cannot_see_other_section_announcement_on_dashboard(self):
        ann = Announcement.objects.create(
            course=self.course, title='Section B Notice',
            content='Section B only', priority='low', created_by=self.faculty,
        )
        ann.sections.add(self.section_b)
        response = self.student1_client.get(reverse('student_dashboard'))
        self.assertNotContains(response, 'Section B Notice')


# ─────────────────────────────────────────────────────────────────────────────
# 5. FACULTY SECTION ASSIGNMENT FEATURES
# ─────────────────────────────────────────────────────────────────────────────
class FacultySectionAssignmentTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        self.section = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )
        self.section.faculty.add(self.faculty)

    def test_add_student_with_section_id_enrolls_and_assigns(self):
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({
                'email': self.student1.email,
                'section_id': self.section.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Enrollment.objects.filter(student=self.student1, course=self.course).exists()
        )
        self.assertIn(self.student1, self.section.students.all())

    def test_add_student_without_section_id_enrolls_only(self):
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({'email': self.student1.email}),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Enrollment.objects.filter(student=self.student1, course=self.course).exists()
        )
        self.assertNotIn(self.student1, self.section.students.all())

    def test_add_student_with_nonexistent_section_id_still_enrolls(self):
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({'email': self.student1.email, 'section_id': 99999}),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        self.assertTrue(
            Enrollment.objects.filter(student=self.student1, course=self.course).exists()
        )

    def test_add_student_with_other_faculty_section_does_not_assign(self):
        """Faculty cannot assign to a section they don't teach."""
        other_section = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )
        # other_section has no faculty assigned to self.faculty
        response = self.faculty_client.post(
            reverse('add_student_to_course', args=[self.course.id]),
            data=json.dumps({
                'email': self.student1.email,
                'section_id': other_section.id,
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        # Student enrolled in course but NOT in other_section
        self.assertNotIn(self.student1, other_section.students.all())

    def test_add_students_by_range_with_section_id_assigns_all(self):
        response = self.faculty_client.post(
            reverse('add_students_by_range', args=[self.course.id]),
            data=json.dumps({
                'from_id': 20230001,
                'to_id': 20230002,
                'section_id': self.section.id,
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['added'], 2)
        self.assertIn(self.student1, self.section.students.all())
        self.assertIn(self.student2, self.section.students.all())

    def test_add_students_by_range_without_section_id_does_not_assign(self):
        response = self.faculty_client.post(
            reverse('add_students_by_range', args=[self.course.id]),
            data=json.dumps({'from_id': 20230001, 'to_id': 20230001}),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        self.assertNotIn(self.student1, self.section.students.all())

    def test_add_students_by_range_already_enrolled_also_assigned_to_section(self):
        """Already-enrolled students should still be assigned to the section."""
        Enrollment.objects.create(student=self.student1, course=self.course)
        response = self.faculty_client.post(
            reverse('add_students_by_range', args=[self.course.id]),
            data=json.dumps({
                'from_id': 20230001,
                'to_id': 20230001,
                'section_id': self.section.id,
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['already_enrolled'], 1)
        self.assertIn(self.student1, self.section.students.all())


# ─────────────────────────────────────────────────────────────────────────────
# 6. CREATE ASSIGNMENT WITH SECTION IDS (bug fix test)
# ─────────────────────────────────────────────────────────────────────────────
class CreateAssignmentSectionTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        self.section = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )

    def test_create_assignment_with_section_ids_targets_section(self):
        response = self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Section Targeted HW',
                'assessment_type': 'assignment',
                'due_date': '2026-12-31',
                'publish_immediately': True,
                'section_ids': [self.section.id],
                'questions': [{'text': 'Q1', 'max_marks': 10}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        hw = Assessment.objects.get(title='Section Targeted HW')
        self.assertIn(self.section, hw.sections.all())

    def test_create_assignment_no_section_ids_is_course_wide(self):
        response = self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Course Wide HW',
                'assessment_type': 'assignment',
                'due_date': '2026-12-31',
                'publish_immediately': True,
                'section_ids': [],
                'questions': [{'text': 'Q1', 'max_marks': 5}],
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        hw = Assessment.objects.get(title='Course Wide HW')
        self.assertEqual(hw.sections.count(), 0)

    def test_create_assignment_with_multiple_section_ids(self):
        sec_b = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )
        response = self.faculty_client.post(
            reverse('create_assignment'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Multi-Section HW',
                'assessment_type': 'assignment',
                'due_date': '2026-12-31',
                'section_ids': [self.section.id, sec_b.id],
                'questions': [{'text': 'Q1', 'max_marks': 5}],
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        hw = Assessment.objects.get(title='Multi-Section HW')
        self.assertIn(self.section, hw.sections.all())
        self.assertIn(sec_b, hw.sections.all())


# ─────────────────────────────────────────────────────────────────────────────
# 7. ANNOUNCEMENT SECTION TARGETING TESTS
# ─────────────────────────────────────────────────────────────────────────────
class AnnouncementSectionTargetingTests(SectionBaseTestCase):
    def setUp(self):
        super().setUp()
        self.section_a = Section.objects.create(
            course=self.course, name='A', batch='Fall 2025',
        )
        self.section_b = Section.objects.create(
            course=self.course, name='B', batch='Fall 2025',
        )

    def test_create_announcement_with_section_id_targets_it(self):
        response = self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Targeted Ann',
                'content': 'For section A only',
                'priority': 'medium',
                'section_ids': [self.section_a.id],
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        ann = Announcement.objects.get(title='Targeted Ann')
        self.assertIn(self.section_a, ann.sections.all())
        self.assertNotIn(self.section_b, ann.sections.all())

    def test_create_announcement_no_sections_is_course_wide(self):
        response = self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Course Wide Ann',
                'content': 'For everyone',
                'priority': 'low',
                'section_ids': [],
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        ann = Announcement.objects.get(title='Course Wide Ann')
        self.assertEqual(ann.sections.count(), 0)

    def test_create_announcement_multiple_sections(self):
        response = self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Multi-Section Ann',
                'content': 'For A and B',
                'priority': 'high',
                'section_ids': [self.section_a.id, self.section_b.id],
            }),
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        ann = Announcement.objects.get(title='Multi-Section Ann')
        self.assertIn(self.section_a, ann.sections.all())
        self.assertIn(self.section_b, ann.sections.all())

    def test_announcement_section_notification_sent_to_enrolled(self):
        Enrollment.objects.create(student=self.student1, course=self.course)
        Notification.objects.filter(recipient=self.student1).delete()
        self.faculty_client.post(
            reverse('create_announcement'),
            data=json.dumps({
                'course_id': self.course.id,
                'title': 'Notif Ann',
                'content': 'content',
                'priority': 'medium',
                'section_ids': [],
            }),
            content_type='application/json',
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student1, notif_type='announcement',
            ).exists()
        )
