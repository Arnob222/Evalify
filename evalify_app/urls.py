from django.urls import path
from . import views

urlpatterns = [
    #Auth
    path('', views.home, name='home'),
    path('signin/', views.sign_in_html, name='sign_in_html'),
    path('signup/', views.sign_up_html, name='sign_up_html'),
    path('signout/', views.sign_out, name='sign_out'),

    #Faculty 
    path('faculty/dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('faculty/courses/', views.faculty_courses, name='faculty_courses'),
    path('faculty/enrolled-students/', views.faculty_enrolled_students, name='faculty_enrolled_students'),
    path('faculty/courses/add/', views.add_course, name='add_course'),
    path('faculty/courses/<int:course_id>/archive/', views.archive_course, name='archive_course'),
    path('faculty/courses/<int:course_id>/add-clo/', views.add_clo, name='add_clo'),
    path('faculty/courses/<int:course_id>/clos/', views.get_course_clos, name='get_course_clos'),
    path('faculty/courses/<int:course_id>/add-student/', views.add_student_to_course, name='add_student_to_course'),
    path('faculty/courses/<int:course_id>/remove-student/<int:student_id>/', views.remove_student_from_course, name='remove_student_from_course'),
    path('faculty/courses/<int:course_id>/add-students-range/', views.add_students_by_range, name='add_students_by_range'),
    path('faculty/clo/<int:clo_id>/delete/', views.delete_clo, name='delete_clo'),
    path('faculty/assessments/', views.faculty_assessments, name='faculty_assessments'),
    path('faculty/assessments/create/', views.create_assessment, name='create_assessment'),
    path('faculty/grading/', views.faculty_grading, name='faculty_grading'),
    path('faculty/grading/<int:sub_id>/', views.get_submission_detail, name='submission_detail'),
    path('faculty/grading/<int:sub_id>/grade/', views.grade_submission, name='grade_submission'),
    path('faculty/analytics/', views.faculty_analytics, name='faculty_analytics'),
    path('faculty/plo-comparison/', views.faculty_plo_comparison, name='faculty_plo_comparison'),
    path('faculty/escar/', views.faculty_escar, name='faculty_escar'),
    path('faculty/escar/save-plan/', views.save_escar_plan, name='save_escar_plan'),
    path('faculty/announcements/', views.faculty_announcements, name='faculty_announcements'),
    path('faculty/announcements/create/', views.create_announcement, name='create_announcement'),
    path('faculty/announcements/<int:ann_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('faculty/plo/add/', views.add_plo, name='add_plo'), 

    #Faculty Assignments
    path('faculty/assignments/', views.faculty_assignments, name='faculty_assignments'),
    path('faculty/assignments/create/', views.create_assignment, name='create_assignment'),
    path('faculty/assignments/<int:assignment_id>/delete/', views.delete_assignment, name='delete_assignment'),
    path('faculty/assignments/<int:assignment_id>/data/', views.get_assessment_data, name='get_assessment_data'),
    path('faculty/assignments/<int:assignment_id>/edit/', views.edit_assessment, name='edit_assessment'),
    path('faculty/assignments/<int:assignment_id>/publish/', views.publish_assessment, name='publish_assessment'),

    #Marks Sheet
    path('faculty/marks-sheet/', views.faculty_marks_sheet, name='faculty_marks_sheet'),
    path('faculty/grades/update/', views.update_question_grade, name='update_question_grade'),

    #Study Materials
    path('faculty/materials/', views.faculty_materials, name='faculty_materials'),
    path('faculty/materials/upload/', views.upload_material, name='upload_material'),
    path('faculty/materials/<int:material_id>/delete/', views.delete_material, name='delete_material'),
    path('student/materials/', views.student_materials, name='student_materials'),
    path('faculty/materials/<int:material_id>/toggle/', views.toggle_material_visibility, name='toggle_material_visibility'),

    #Student
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/courses/', views.student_courses, name='student_courses'),
    path('student/courses/enroll-code/', views.enroll_via_code, name='enroll_via_code'),
    path('student/courses/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    path('student/courses/<int:course_id>/unenroll/', views.unenroll_course, name='unenroll_course'),
    path('student/submissions/', views.student_submissions, name='student_submissions'),
    path('student/submissions/<int:assessment_id>/submit/', views.submit_assessment, name='submit_assessment'),
    path('student/clo-results/', views.student_clo_results, name='student_clo_results'),
    path('student/notifications/',              views.student_notifications, name='student_notifications'),
    path('student/notifications/unread-count/', views.get_unread_count,      name='get_unread_count'),
    path('student/notifications/mark-all-read/',views.mark_all_read,         name='mark_all_read'),
    path('student/assignments/', views.student_assignments, name='student_assignments'),
    path('student/assignments/course/<int:course_id>/', views.student_course_assignments, name='student_course_assignments'),
    path('student/assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('student/assignments/<int:assignment_id>/unsubmit/', views.unsubmit_assignment, name='unsubmit_assignment'),

    # Question Bank — Faculty
    path('faculty/question-bank/',                        views.faculty_question_bank,   name='faculty_question_bank'),
    path('faculty/question-bank/create/',                 views.create_past_paper,       name='create_past_paper'),
    path('faculty/question-bank/<int:paper_id>/delete/',  views.delete_past_paper,       name='delete_past_paper'),
    path('faculty/question-bank/<int:paper_id>/toggle/',  views.toggle_paper_visibility, name='toggle_paper_visibility'),
    path('faculty/question-bank/hint/<int:question_id>/', views.toggle_hint_visibility,  name='toggle_hint_visibility'),

    # Question Bank — Student
    path('student/question-bank/',                                           views.student_question_bank,  name='student_question_bank'),
    path('student/question-bank/<int:paper_id>/',                            views.student_view_paper,     name='student_view_paper'),
    path('student/question-bank/course/<int:course_id>/',                    views.student_qbank_course,   name='student_qbank_course'),
    path('student/question-bank/course/<int:course_id>/<str:atype>/',        views.student_qbank_type,     name='student_qbank_type'),



# Admin Portal
    path('admin-portal/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-portal/users/', views.admin_users, name='admin_users'),
    path('admin-portal/users/create/', views.admin_create_user, name='admin_create_user'),
    path('admin-portal/users/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-portal/users/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    path('admin-portal/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-portal/courses/', views.admin_courses, name='admin_courses'),
    path('admin-portal/courses/<int:course_id>/delete/', views.admin_delete_course, name='admin_delete_course'),
    path('admin-portal/assessments/', views.admin_assessments, name='admin_assessments'),
    path('admin-portal/assessments/<int:assessment_id>/delete/', views.admin_delete_assessment, name='admin_delete_assessment'),
    path('admin-portal/submissions/', views.admin_submissions, name='admin_submissions'),
    path('admin-portal/announcements/', views.admin_announcements, name='admin_announcements'),
    path('admin-portal/announcements/<int:ann_id>/delete/', views.admin_delete_announcement, name='admin_delete_announcement'),
    path('admin-portal/materials/', views.admin_materials, name='admin_materials'),
    path('admin-portal/materials/<int:material_id>/delete/', views.admin_delete_material, name='admin_delete_material'),


# DOA Portal
    path('doa-portal/', views.doa_dashboard, name='doa_dashboard'),
    path('doa-portal/users/', views.doa_users, name='doa_users'),
    path('doa-portal/users/create/', views.doa_create_user, name='doa_create_user'),
    path('doa-portal/users/<int:user_id>/edit/', views.doa_edit_user, name='doa_edit_user'),
    path('doa-portal/users/<int:user_id>/toggle/', views.doa_toggle_user, name='doa_toggle_user'),
    path('doa-portal/users/<int:user_id>/delete/', views.doa_delete_user, name='doa_delete_user'),
    path('doa-portal/courses/', views.doa_courses, name='doa_courses'),
    path('doa-portal/courses/create/', views.doa_create_course, name='doa_create_course'),
    path('doa-portal/courses/<int:course_id>/assign-faculty/', views.doa_assign_faculty, name='doa_assign_faculty'),
    path('doa-portal/courses/<int:course_id>/assign/', views.doa_assign_faculty_page, name='doa_assign_faculty_page'),
    path('doa-portal/courses/<int:course_id>/toggle-active/', views.doa_toggle_course_active, name='doa_toggle_course_active'),
    path('doa-portal/courses/<int:course_id>/delete/', views.doa_delete_course, name='doa_delete_course'),
    path('doa-portal/analytics/', views.doa_analytics, name='doa_analytics'),
    path('doa-portal/students/', views.doa_students, name='doa_students'),
    path('doa-portal/students/<int:student_id>/attainment/', views.doa_student_attainment, name='doa_student_attainment'),
    path('doa-portal/sections/', views.doa_sections, name='doa_sections'),
    path('doa-portal/sections/create/', views.doa_create_section, name='doa_create_section'),
    path('doa-portal/sections/<int:section_id>/', views.doa_section_detail, name='doa_section_detail'),
    path('doa-portal/sections/<int:section_id>/assign-faculty/', views.doa_section_assign_faculty, name='doa_section_assign_faculty'),
    path('doa-portal/sections/<int:section_id>/assign-students/', views.doa_section_assign_students, name='doa_section_assign_students'),
    path('doa-portal/sections/<int:section_id>/remove-student/<int:student_id>/', views.doa_section_remove_student, name='doa_section_remove_student'),
    path('doa-portal/sections/<int:section_id>/delete/', views.doa_delete_section, name='doa_delete_section'),

# Assessment Download
    path('faculty/assignments/<int:assessment_id>/download/<str:fmt>/', views.download_assessment, name='download_assessment'),


]