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
    path('faculty/semester-plo-comparison/', views.faculty_semester_plo_comparison, name='faculty_semester_plo_comparison'),
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
    path('admin-portal/escar/', views.admin_escar, name='admin_escar'),


# DAO Portal
    path('dao-portal/', views.dao_dashboard, name='dao_dashboard'),
    path('dao-portal/users/', views.dao_users, name='dao_users'),
    path('dao-portal/users/create/', views.dao_create_user, name='dao_create_user'),
    path('dao-portal/users/<int:user_id>/edit/', views.dao_edit_user, name='dao_edit_user'),
    path('dao-portal/users/<int:user_id>/toggle/', views.dao_toggle_user, name='dao_toggle_user'),
    path('dao-portal/users/<int:user_id>/delete/', views.dao_delete_user, name='dao_delete_user'),
    path('dao-portal/courses/', views.dao_courses, name='dao_courses'),
    path('dao-portal/courses/create/', views.dao_create_course, name='dao_create_course'),
    path('dao-portal/courses/<int:course_id>/assign-faculty/', views.dao_assign_faculty, name='dao_assign_faculty'),
    path('dao-portal/courses/<int:course_id>/assign/', views.dao_assign_faculty_page, name='dao_assign_faculty_page'),
    path('dao-portal/courses/<int:course_id>/toggle-active/', views.dao_toggle_course_active, name='dao_toggle_course_active'),
    path('dao-portal/courses/<int:course_id>/delete/', views.dao_delete_course, name='dao_delete_course'),
    path('dao-portal/analytics/', views.dao_analytics, name='dao_analytics'),
    path('dao-portal/escar/', views.dao_escar, name='dao_escar'),
    path('dao-portal/students/', views.dao_students, name='dao_students'),
    path('dao-portal/students/<int:student_id>/attainment/', views.dao_student_attainment, name='dao_student_attainment'),
    path('dao-portal/sections/', views.dao_sections, name='dao_sections'),
    path('dao-portal/sections/create/', views.dao_create_section, name='dao_create_section'),
    path('dao-portal/sections/<int:section_id>/', views.dao_section_detail, name='dao_section_detail'),
    path('dao-portal/sections/<int:section_id>/assign-faculty/', views.dao_section_assign_faculty, name='dao_section_assign_faculty'),
    path('dao-portal/sections/<int:section_id>/assign-students/', views.dao_section_assign_students, name='dao_section_assign_students'),
    path('dao-portal/sections/<int:section_id>/add-single-student/', views.dao_section_add_single_student, name='dao_section_add_single_student'),
    path('dao-portal/sections/<int:section_id>/remove-student/<int:student_id>/', views.dao_section_remove_student, name='dao_section_remove_student'),
    path('dao-portal/sections/<int:section_id>/delete/', views.dao_delete_section, name='dao_delete_section'),

# Department Head Portal
    path('dept-head/', views.dept_head_dashboard, name='dept_head_dashboard'),
    path('dept-head/users/', views.dept_head_users, name='dept_head_users'),
    path('dept-head/users/create/', views.dept_head_create_user, name='dept_head_create_user'),
    path('dept-head/users/<int:user_id>/edit/', views.dept_head_edit_user, name='dept_head_edit_user'),
    path('dept-head/users/<int:user_id>/toggle/', views.dept_head_toggle_user, name='dept_head_toggle_user'),
    path('dept-head/users/<int:user_id>/delete/', views.dept_head_delete_user, name='dept_head_delete_user'),
    path('dept-head/courses/', views.dept_head_courses, name='dept_head_courses'),
    path('dept-head/courses/create/', views.dept_head_create_course, name='dept_head_create_course'),
    path('dept-head/courses/<int:course_id>/assign-faculty/', views.dept_head_assign_faculty, name='dept_head_assign_faculty'),
    path('dept-head/courses/<int:course_id>/assign/', views.dept_head_assign_faculty_page, name='dept_head_assign_faculty_page'),
    path('dept-head/courses/<int:course_id>/toggle-active/', views.dept_head_toggle_course_active, name='dept_head_toggle_course_active'),
    path('dept-head/courses/<int:course_id>/delete/', views.dept_head_delete_course, name='dept_head_delete_course'),
    path('dept-head/analytics/', views.dept_head_analytics, name='dept_head_analytics'),
    path('dept-head/escar/', views.dept_head_escar, name='dept_head_escar'),
    path('dept-head/students/', views.dept_head_students, name='dept_head_students'),
    path('dept-head/students/<int:student_id>/attainment/', views.dept_head_student_attainment, name='dept_head_student_attainment'),
    path('dept-head/sections/', views.dept_head_sections, name='dept_head_sections'),
    path('dept-head/sections/create/', views.dept_head_create_section, name='dept_head_create_section'),
    path('dept-head/sections/<int:section_id>/', views.dept_head_section_detail, name='dept_head_section_detail'),
    path('dept-head/sections/<int:section_id>/assign-faculty/', views.dept_head_section_assign_faculty, name='dept_head_section_assign_faculty'),
    path('dept-head/sections/<int:section_id>/assign-students/', views.dept_head_section_assign_students, name='dept_head_section_assign_students'),
    path('dept-head/sections/<int:section_id>/add-single-student/', views.dept_head_section_add_single_student, name='dept_head_section_add_single_student'),
    path('dept-head/sections/<int:section_id>/remove-student/<int:student_id>/', views.dept_head_section_remove_student, name='dept_head_section_remove_student'),
    path('dept-head/sections/<int:section_id>/delete/', views.dept_head_delete_section, name='dept_head_delete_section'),

# Assessment Download
    path('faculty/assignments/<int:assessment_id>/download/<str:fmt>/', views.download_assessment, name='download_assessment'),
    

# Batch Analytics
    path('faculty/batch-analytics/', views.faculty_batch_analytics, name='faculty_batch_analytics'),
    path('dao-portal/batch-analytics/', views.dao_batch_analytics, name='dao_batch_analytics'),
    path('dept-head/batch-analytics/', views.dept_head_batch_analytics, name='dept_head_batch_analytics'),

]