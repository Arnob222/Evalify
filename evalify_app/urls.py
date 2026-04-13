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
    path('faculty/courses/add/', views.add_course, name='add_course'),
    path('faculty/courses/<int:course_id>/add-clo/', views.add_clo, name='add_clo'),
    path('faculty/courses/<int:course_id>/clos/', views.get_course_clos, name='get_course_clos'),
    path('faculty/courses/<int:course_id>/add-student/', views.add_student_to_course, name='add_student_to_course'),
    path('faculty/clo/<int:clo_id>/delete/', views.delete_clo, name='delete_clo'),
    path('faculty/assessments/', views.faculty_assessments, name='faculty_assessments'),
    path('faculty/assessments/create/', views.create_assessment, name='create_assessment'),
    path('faculty/grading/', views.faculty_grading, name='faculty_grading'),
    path('faculty/grading/<int:sub_id>/', views.get_submission_detail, name='submission_detail'),
    path('faculty/grading/<int:sub_id>/grade/', views.grade_submission, name='grade_submission'),
    path('faculty/analytics/', views.faculty_analytics, name='faculty_analytics'),
    path('faculty/announcements/', views.faculty_announcements, name='faculty_announcements'),
    path('faculty/announcements/create/', views.create_announcement, name='create_announcement'),
    path('faculty/announcements/<int:ann_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('faculty/plo/add/', views.add_plo, name='add_plo'), 

    #Faculty Assignments
    path('faculty/assignments/', views.faculty_assignments, name='faculty_assignments'),
    path('faculty/assignments/create/', views.create_assignment, name='create_assignment'),
    path('faculty/assignments/<int:assignment_id>/delete/', views.delete_assignment, name='delete_assignment'),
    path('faculty/assignments/<int:assignment_id>/publish/', views.publish_assessment, name='publish_assessment'),

    #Study Materials
    path('faculty/materials/', views.faculty_materials, name='faculty_materials'),
    path('faculty/materials/upload/', views.upload_material, name='upload_material'),
    path('faculty/materials/<int:material_id>/delete/', views.delete_material, name='delete_material'),
    path('student/materials/', views.student_materials, name='student_materials'),
    path('faculty/materials/<int:material_id>/toggle/', views.toggle_material_visibility, name='toggle_material_visibility'),

    #Student
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/courses/', views.student_courses, name='student_courses'),
    path('student/courses/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    path('student/submissions/', views.student_submissions, name='student_submissions'),
    path('student/submissions/<int:assessment_id>/submit/', views.submit_assessment, name='submit_assessment'),
    path('student/clo-results/', views.student_clo_results, name='student_clo_results'),
    path('student/notifications/', views.student_notifications, name='student_notifications'),
    path('student/assignments/', views.student_assignments, name='student_assignments'),
    path('student/assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
]
