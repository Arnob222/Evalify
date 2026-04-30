from django.contrib.auth.models import AbstractUser
from django.db import models
import random
import string


class User(AbstractUser):
    ROLE_CHOICES = [
        ('faculty', 'Faculty'),
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='')
    full_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.full_name or self.username} ({self.role})"


class PLO(models.Model):
    code = models.CharField(max_length=20)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.code


class Course(models.Model):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credit_hours = models.IntegerField(default=3)
    semester = models.CharField(max_length=50, default='Fall 2025')
    faculty = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    created_at = models.DateTimeField(auto_now_add=True)
    enrollment_code = models.CharField(max_length=8, unique=True, blank=True, default='')
    is_archived = models.BooleanField(default=False)

    def _gen_code(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=6))
            if not Course.objects.filter(enrollment_code=code).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.enrollment_code:
            self.enrollment_code = self._gen_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}: {self.name}"


class CLO(models.Model):
    BLOOM_CHOICES = [
        ('Remember (L1)', 'Remember (L1)'),
        ('Understand (L2)', 'Understand (L2)'),
        ('Apply (L3)', 'Apply (L3)'),
        ('Analyze (L4)', 'Analyze (L4)'),
        ('Evaluate (L5)', 'Evaluate (L5)'),
        ('Create (L6)', 'Create (L6)'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='clos')
    code = models.CharField(max_length=20)
    description = models.TextField()
    bloom_level = models.CharField(max_length=30, choices=BLOOM_CHOICES)
    plos = models.ManyToManyField(PLO, blank=True)

    def __str__(self):
        return f"{self.course.code} - {self.code}"


class Assessment(models.Model):
    TYPE_CHOICES = [
        ('assignment', 'Assignment'),
        ('quiz', 'Quiz'),
        ('mid', 'Mid Exam'),
        ('ct', 'Class Test'),
        ('final', 'Final Exam'),
        ('lab', 'Lab Task'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assessment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='published')
    total_marks = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # ── Grace period fields ───────────────────────────────────────────────
    grace_period_hours   = models.IntegerField(default=0)
    late_deduction_type  = models.CharField(max_length=10, default='percent',
                               choices=[('percent','Percent'),('flat','Flat Marks')])
    late_deduction_value = models.FloatField(default=0)
    max_late_days        = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.title} ({self.course.code})"


class Question(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    order = models.IntegerField(default=1)
    text = models.TextField()
    image = models.FileField(upload_to='questions/', blank=True, null=True)
    max_marks = models.IntegerField(default=10)
    clos = models.ManyToManyField(CLO, blank=True)
    plos = models.ManyToManyField(PLO, blank=True)

    def __str__(self):
        return f"Q{self.order} - {self.assessment.title}"


class SubQuestion(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='sub_questions')
    order = models.IntegerField(default=1)
    text = models.TextField()
    image = models.FileField(upload_to='sub_questions/', blank=True, null=True)
    max_marks = models.IntegerField(default=5)
    clos = models.ManyToManyField(CLO, blank=True)
    plos = models.ManyToManyField(PLO, blank=True)

    def __str__(self):
        return f"Sub-Q{self.order} of Q{self.question.order} ({self.question.assessment.title})"


class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')


class Submission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('flagged', 'Flagged'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='submissions')
    content = models.TextField(blank=True)
    submitted_file = models.FileField(upload_to='submissions/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    total_score = models.FloatField(default=0)
    feedback = models.TextField(blank=True)
    plagiarism_score = models.FloatField(default=0)
    ai_content_score = models.FloatField(default=0)
    # ── Late submission tracking ──────────────────────────────────────────
    is_late       = models.BooleanField(default=False)
    hours_late    = models.FloatField(default=0)
    late_deduction = models.FloatField(default=0)
    final_score   = models.FloatField(default=0)

    class Meta:
        unique_together = ('student', 'assessment')


class QuestionGrade(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='question_grades')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    marks_obtained = models.FloatField(default=0)

    class Meta:
        unique_together = ('submission', 'question')


class SubQuestionGrade(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='sub_question_grades')
    sub_question = models.ForeignKey(SubQuestion, on_delete=models.CASCADE)
    marks_obtained = models.FloatField(default=0)

    class Meta:
        unique_together = ('submission', 'sub_question')


class StudyMaterial(models.Model):
    MATERIAL_TYPE_CHOICES = [
        ('lecture_note', 'Lecture Note'),
        ('reference',    'Reference Material'),
        ('video',        'Reference Video'),
        ('assignment',   'Assignment Sheet'),
        ('other',        'Other'),
    ]

    course        = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title         = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPE_CHOICES, default='lecture_note')
    file          = models.FileField(upload_to='materials/', blank=True, null=True)
    video_url     = models.URLField(blank=True)
    uploaded_by   = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    is_visible    = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.course.code})"

    def filename(self):
        if self.file:
            return self.file.name.split('/')[-1]
        return ''

    def is_video(self):
        return self.material_type == 'video' or bool(self.video_url)

    def embed_url(self):
        """Convert YouTube watch URL → embed URL for iframe."""
        import re
        url = self.video_url
        if not url:
            return ''
        m = re.match(r'https?://youtu\.be/([^?&]+)', url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
        m = re.search(r'[?&]v=([^&]+)', url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
        return url  


class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Notification(models.Model):
    NOTIF_TYPE_CHOICES = [
        ('grade_released',    'Grade Released'),
        ('deadline_tomorrow', 'Deadline Tomorrow'),
        ('deadline_today',    'Due Today'),
        ('new_assignment',    'New Assignment'),
        ('new_material',      'New Material'),
        ('announcement',      'Announcement'),
    ]

    recipient  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPE_CHOICES)
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    course     = models.ForeignKey(Course,     on_delete=models.CASCADE, null=True, blank=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, null=True, blank=True)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notif_type} → {self.recipient.username}"

    @classmethod
    def send(cls, recipient, notif_type, title, message,
             course=None, assessment=None, submission=None):
        from django.utils import timezone
        from datetime import timedelta
        one_min_ago = timezone.now() - timedelta(minutes=1)
        already = cls.objects.filter(
            recipient=recipient,
            notif_type=notif_type,
            title=title,
            created_at__gte=one_min_ago,
        ).exists()
        if not already:
            cls.objects.create(
                recipient=recipient,
                notif_type=notif_type,
                title=title,
                message=message,
                course=course,
                assessment=assessment,
                submission=submission,
            )





class PastPaper(models.Model):
    EXAM_TYPE_CHOICES = [
        ('mid',        'Mid Exam'),
        ('final',      'Final Exam'),
        ('ct',         'Class Test'),
        ('quiz',       'Quiz'),
        ('assignment', 'Assignment'),
    ]
 
    title           = models.CharField(max_length=200)
    course_code     = models.CharField(max_length=20)
    course_name     = models.CharField(max_length=200)
    semester        = models.CharField(max_length=50)
    exam_type       = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    total_marks     = models.IntegerField(default=0)
    duration_mins   = models.IntegerField(default=0)
    description     = models.TextField(blank=True)
 
    # Privacy
    is_public       = models.BooleanField(default=False,
        help_text='True = all enrolled students can access')
    allowed_courses = models.ManyToManyField('Course', blank=True,
        related_name='past_papers',
        help_text='If not public, only students in these courses can access')
 
    uploaded_by     = models.ForeignKey(User, on_delete=models.CASCADE,
        related_name='past_papers')
    uploaded_at     = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-uploaded_at']
 
    def __str__(self):
        return f"{self.course_code} | {self.semester} | {self.get_exam_type_display()}"
 
 
class CLOActionPlan(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='clo_action_plans')
    clo = models.ForeignKey(CLO, on_delete=models.CASCADE, related_name='action_plans')
    action_plan = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('course', 'clo')


class PLOActionPlan(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='plo_action_plans')
    plo = models.ForeignKey(PLO, on_delete=models.CASCADE, related_name='action_plans')
    action_plan = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('course', 'plo')


class PastPaperQuestion(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy',   'Easy'),
        ('medium', 'Medium'),
        ('hard',   'Hard'),
    ]
 
    paper       = models.ForeignKey(PastPaper, on_delete=models.CASCADE,
                    related_name='questions')
    order       = models.IntegerField(default=1)
    text        = models.TextField()
    marks       = models.IntegerField(default=0)
    answer_hint = models.TextField(blank=True)
    show_hint   = models.BooleanField(default=False)
    topic_tag   = models.CharField(max_length=100, blank=True)
    difficulty  = models.CharField(max_length=10, blank=True,
                    choices=DIFFICULTY_CHOICES)
 
    class Meta:
        ordering = ['order']
 
    def __str__(self):
        return f"Q{self.order} — {self.paper}"
 