from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('faculty', 'Faculty'),
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
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
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assessment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='published')
    total_marks = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.course.code})"


class Question(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    order = models.IntegerField(default=1)
    text = models.TextField()
    max_marks = models.IntegerField(default=10)
    clos = models.ManyToManyField(CLO, blank=True)
    plos = models.ManyToManyField(PLO, blank=True)

    def __str__(self):
        return f"Q{self.order} - {self.assessment.title}"


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

    class Meta:
        unique_together = ('student', 'assessment')


class QuestionGrade(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='question_grades')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    marks_obtained = models.FloatField(default=0)

    class Meta:
        unique_together = ('submission', 'question')


class StudyMaterial(models.Model):
    MATERIAL_TYPE_CHOICES = [
        ('lecture_note', 'Lecture Note'),
        ('reference',    'Reference Material'),
        ('video',        'Reference Video'),
        ('assignment',   'Assignment Sheet'),
        ('other',        'Other'),
    ]
 
    course       = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPE_CHOICES, default='lecture_note')
 
    # File upload (for notes, PDFs, slides etc.)
    file         = models.FileField(upload_to='materials/', blank=True, null=True)
 
    # Video URL (YouTube / Google Drive / any link)
    video_url    = models.URLField(blank=True)
 
    uploaded_by  = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at  = models.DateTimeField(auto_now_add=True)
 
    # Visibility — faculty can hide a material temporarily
    is_visible   = models.BooleanField(default=True)
 
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
        # youtu.be/ID
        m = re.match(r'https?://youtu\.be/([^?&]+)', url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
        # youtube.com/watch?v=ID
        m = re.search(r'[?&]v=([^&]+)', url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
        # Already an embed URL or other platform — return as-is


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