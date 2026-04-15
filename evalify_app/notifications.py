
from .models import Notification, Enrollment, Submission
 
 
def notify_grade_released(submission):
    """Grade publish হলে student কে notify করো।"""
    student    = submission.student
    assessment = submission.assessment
    course     = assessment.course
    score      = f"{int(submission.total_score)}/{assessment.total_marks}"
    pct        = round(
        submission.total_score / assessment.total_marks * 100, 1
    ) if assessment.total_marks else 0
 
    Notification.send(
        recipient  = student,
        notif_type = 'grade_released',
        title      = f"Grade Released: {assessment.title}",
        message    = (
            f"Your grade for '{assessment.title}' in {course.code} has been published. "
            f"Score: {score} ({pct}%)."
            + (f" Feedback: {submission.feedback}" if submission.feedback else "")
        ),
        course     = course,
        assessment = assessment,
        submission = submission,
    )
 
 
def notify_new_assignment(assessment):
    """Assignment publish হলে সব enrolled students কে notify করো।"""
    course      = assessment.course
    enrollments = Enrollment.objects.filter(course=course).select_related('student')
    due_str     = str(assessment.due_date) if assessment.due_date else 'No deadline'
 
    for enroll in enrollments:
        Notification.send(
            recipient  = enroll.student,
            notif_type = 'new_assignment',
            title      = f"New {assessment.get_assessment_type_display()}: {assessment.title}",
            message    = (
                f"A new {assessment.get_assessment_type_display().lower()} has been posted "
                f"in {course.code}. Due: {due_str}. Total marks: {assessment.total_marks}."
            ),
            course     = course,
            assessment = assessment,
        )
 
 
def notify_new_material(material):
    """Study material upload হলে সব enrolled students কে notify করো।"""
    course      = material.course
    enrollments = Enrollment.objects.filter(course=course).select_related('student')
 
    for enroll in enrollments:
        Notification.send(
            recipient  = enroll.student,
            notif_type = 'new_material',
            title      = f"New Material: {material.title}",
            message    = (
                f"New study material '{material.title}' has been uploaded "
                f"for {course.code} ({material.get_material_type_display()})."
                + (f" {material.description}" if material.description else "")
            ),
            course = course,
        )
 
 
def notify_announcement(announcement):
    """Announcement create হলে সব enrolled students কে notify করো।"""
    course      = announcement.course
    enrollments = Enrollment.objects.filter(course=course).select_related('student')
 
    for enroll in enrollments:
        Notification.send(
            recipient  = enroll.student,
            notif_type = 'announcement',
            title      = f"📢 {announcement.title}",
            message    = announcement.content,
            course     = course,
        )
 
 
def send_deadline_reminders():
    """
    Daily cron এ চালাও।
    Due today বা tomorrow এমন assignments এর জন্য reminder পাঠায়।
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import Assessment
 
    today    = timezone.now().date()
    tomorrow = today + timedelta(days=1)
 
    for assessment in Assessment.objects.filter(
        due_date__in=[today, tomorrow],
        status='published',
    ).select_related('course'):
        is_today   = assessment.due_date == today
        notif_type = 'deadline_today' if is_today else 'deadline_tomorrow'
        label      = 'TODAY' if is_today else 'tomorrow'
 
        for enroll in Enrollment.objects.filter(
            course=assessment.course
        ).select_related('student'):
            # already submitted? skip
            if Submission.objects.filter(
                student=enroll.student, assessment=assessment
            ).exists():
                continue
 
            Notification.send(
                recipient  = enroll.student,
                notif_type = notif_type,
                title      = f"⏰ Due {label}: {assessment.title}",
                message    = (
                    f"Reminder: '{assessment.title}' ({assessment.course.code}) "
                    f"is due {label} ({assessment.due_date}). "
                    f"Total marks: {assessment.total_marks}. Don't forget to submit!"
                ),
                course     = assessment.course,
                assessment = assessment,
            )
 