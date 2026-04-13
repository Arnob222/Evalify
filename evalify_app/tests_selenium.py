
import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class EvalifyFullSeleniumTests(StaticLiveServerTestCase):
    """Complete Selenium test suite for all Evalify pages."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        service = Service(ChromeDriverManager().install())
        cls.driver = webdriver.Chrome(service=service)
        cls.driver.implicitly_wait(10)
        cls.driver.maximize_window()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Clean up previous test users
        User.objects.filter(email='faculty@test.com').delete()
        User.objects.filter(email='student@test.com').delete()
        # Create faculty
        self.faculty_user = User.objects.create_user(
            username='faculty@test.com',
            email='faculty@test.com',
            password='FacultyPass123',
            full_name='Test Faculty',
            role='faculty'
        )
        # Create student
        self.student_user = User.objects.create_user(
            username='student@test.com',
            email='student@test.com',
            password='StudentPass123',
            full_name='Test Student',
            role='student'
        )
        # Create a course for faculty (for announcements, CLOs, etc.)
        try:
            from evalify_app.models import Course
            self.course, _ = Course.objects.get_or_create(
                code='CS-TEST101',
                defaults={
                    'name': 'Selenium Test Course',
                    'description': 'Course for testing',
                    'credit_hours': 3,
                    'semester': 'Fall 2025',
                    'faculty': self.faculty_user
                }
            )
        except ImportError:
            self.course = None

  
    def _login_as_faculty(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('faculty@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('FacultyPass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        WebDriverWait(self.driver, 5).until(
            EC.url_contains('/faculty/dashboard/')
        )

    def _login_as_student(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('student@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('StudentPass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        WebDriverWait(self.driver, 5).until(
            EC.url_contains('/student/dashboard/')
        )
        # Additional wait to ensure dashboard content loads
        time.sleep(1)

    # HOMEPAGE TESTS
    def test_homepage_loads(self):
        self.driver.get(self.live_server_url + '/')
        self.assertIn('Evalify - Smart Assessment Platform', self.driver.title)
        self.assertTrue(self.driver.find_element(By.CSS_SELECTOR, '.badge').is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, 'facultyCard').is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, 'studentCard').is_displayed())

    def test_homepage_navigation_buttons(self):
        self.driver.get(self.live_server_url + '/')
        self.driver.find_element(By.CSS_SELECTOR, '.btn-signup').click()
        self.assertIn('/signup/', self.driver.current_url)
        self.driver.back()
        self.driver.find_element(By.CSS_SELECTOR, '.btn-signin').click()
        self.assertIn('/signin/', self.driver.current_url)

    def test_homepage_features_grid(self):
        self.driver.get(self.live_server_url + '/')
        features = self.driver.find_elements(By.CSS_SELECTOR, '.feature-item')
        self.assertEqual(len(features), 4)
        for feature in features:
            self.assertTrue(feature.find_element(By.TAG_NAME, 'h3').is_displayed())
            self.assertTrue(feature.find_element(By.TAG_NAME, 'p').is_displayed())

    #  SIGN IN TESTS 
    def test_signin_page_elements(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.assertEqual(self.driver.title, 'Evalify - Sign In')
        self.assertTrue(self.driver.find_element(By.NAME, 'email').is_displayed())
        self.assertTrue(self.driver.find_element(By.NAME, 'password').is_displayed())
        self.assertTrue(self.driver.find_element(By.NAME, 'remember').is_displayed())
        self.assertTrue(self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').is_displayed())
        self.assertTrue(self.driver.find_element(By.LINK_TEXT, 'Sign up').is_displayed())

    def test_signin_password_toggle(self):
        self.driver.get(self.live_server_url + '/signin/')
        pwd = self.driver.find_element(By.ID, 'passwordField')
        toggle = self.driver.find_element(By.ID, 'togglePass')
        self.assertEqual(pwd.get_attribute('type'), 'password')
        toggle.click()
        self.assertEqual(pwd.get_attribute('type'), 'text')
        toggle.click()
        self.assertEqual(pwd.get_attribute('type'), 'password')

    def test_signin_success_faculty(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('faculty@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('FacultyPass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        WebDriverWait(self.driver, 5).until(EC.url_contains('/faculty/dashboard/'))
        self.assertIn('/faculty/dashboard/', self.driver.current_url)

    def test_signin_success_student(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('student@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('StudentPass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        WebDriverWait(self.driver, 5).until(EC.url_contains('/student/dashboard/'))
        self.assertIn('/student/dashboard/', self.driver.current_url)

    def test_signin_failure_shows_error(self):
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('wrong@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('wrongpass')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        error_div = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, "//div[contains(@style,'background:rgba(255,80,80')]"))
        )
        self.assertTrue(error_div.is_displayed())
        self.assertIn('/signin/', self.driver.current_url)

    def test_signin_link_to_signup(self):
        self.driver.get(self.live_server_url + '/signin/')
        signup_link = self.driver.find_element(By.CSS_SELECTOR, '.login-link a')
        signup_link.click()
        WebDriverWait(self.driver, 5).until(EC.url_contains('/signup/'))
        self.assertIn('/signup/', self.driver.current_url)

    #  SIGN UP TESTS 
    def test_signup_page_elements(self):
        self.driver.get(self.live_server_url + '/signup/')
        self.assertEqual(self.driver.title, 'Evalify - Create Account')
        self.assertTrue(self.driver.find_element(By.NAME, 'full_name').is_displayed())
        self.assertTrue(self.driver.find_element(By.NAME, 'email').is_displayed())
        self.assertTrue(self.driver.find_element(By.NAME, 'password').is_displayed())
        self.assertTrue(self.driver.find_element(By.XPATH, "//input[@value='student']").is_displayed())
        self.assertTrue(self.driver.find_element(By.XPATH, "//input[@value='faculty']").is_displayed())
        self.assertTrue(self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').is_displayed())

    def test_signup_password_toggle(self):
        self.driver.get(self.live_server_url + '/signup/')
        pwd = self.driver.find_element(By.ID, 'passwordField')
        toggle = self.driver.find_element(By.ID, 'togglePass')
        self.assertEqual(pwd.get_attribute('type'), 'password')
        toggle.click()
        self.assertEqual(pwd.get_attribute('type'), 'text')

    def test_signup_success_student(self):
        self.driver.get(self.live_server_url + '/signup/')
        self.driver.find_element(By.NAME, 'full_name').send_keys('New Student')
        self.driver.find_element(By.NAME, 'email').send_keys('newstudent@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('StrongPass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        WebDriverWait(self.driver, 5).until(
            lambda d: '/signin/' in d.current_url or '/student/dashboard/' in d.current_url
        )
        if '/signin/' in self.driver.current_url:
            self.driver.find_element(By.NAME, 'email').send_keys('newstudent@test.com')
            self.driver.find_element(By.NAME, 'password').send_keys('StrongPass123')
            self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
            WebDriverWait(self.driver, 5).until(EC.url_contains('/student/dashboard/'))
        self.assertIn('/student/dashboard/', self.driver.current_url)

    def test_signup_duplicate_email_error(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user(
            username='duplicate@test.com', email='duplicate@test.com',
            password='pass', full_name='Dupe', role='student'
        )
        self.driver.get(self.live_server_url + '/signup/')
        self.driver.find_element(By.NAME, 'full_name').send_keys('Duplicate User')
        self.driver.find_element(By.NAME, 'email').send_keys('duplicate@test.com')
        self.driver.find_element(By.NAME, 'password').send_keys('SomePass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        error_div = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, "//div[contains(@style,'background:rgba(255,80,80')]"))
        )
        self.assertTrue(error_div.is_displayed())

    def test_signup_link_to_signin(self):
        self.driver.get(self.live_server_url + '/signup/')
        signin_link = self.driver.find_element(By.CSS_SELECTOR, '.login-link a')
        signin_link.click()
        WebDriverWait(self.driver, 5).until(EC.url_contains('/signin/'))
        self.assertIn('/signin/', self.driver.current_url)

    # FACULTY DASHBOARD TESTS
    def test_faculty_dashboard_loads(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/dashboard/')
        self.assertIn('Faculty Dashboard', self.driver.page_source)
        stats = self.driver.find_elements(By.CSS_SELECTOR, '.stat')
        self.assertEqual(len(stats), 4)
        courses_val = self.driver.find_element(By.XPATH, "//div[contains(@class,'stat blue')]//div[@class='stat-val']")
        self.assertEqual(int(courses_val.text), 1)

    def test_faculty_dashboard_panels(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/dashboard/')
        panel1 = self.driver.find_element(By.XPATH, "//div[contains(@class,'panel-title') and text()='Recent Submissions']")
        panel2 = self.driver.find_element(By.XPATH, "//div[contains(@class,'panel-title') and text()='Announcements']")
        self.assertTrue(panel1.is_displayed())
        self.assertTrue(panel2.is_displayed())
        self.assertTrue(self.driver.find_element(By.LINK_TEXT, 'View All').is_displayed())
        self.assertTrue(self.driver.find_element(By.LINK_TEXT, 'Manage').is_displayed())

    # FACULTY ANNOUNCEMENTS TESTS 
    def test_announcements_page_loads(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/announcements/')
        self.assertIn('Announcements', self.driver.page_source)
        self.assertTrue(self.driver.find_element(By.XPATH, "//button[contains(text(),'+ New Announcement')]").is_displayed())

    def test_create_announcement_success(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/announcements/')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ New Announcement')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'newAnnModal')))
        Select(self.driver.find_element(By.ID, 'annCourse')).select_by_value(str(self.course.id))
        self.driver.find_element(By.ID, 'annTitle').send_keys('Selenium Test Announcement')
        self.driver.find_element(By.ID, 'annContent').send_keys('This is a test announcement content.')
        Select(self.driver.find_element(By.ID, 'annPriority')).select_by_value('high')
        self.driver.find_element(By.CSS_SELECTOR, '#newAnnModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Selenium Test Announcement')]"))
        )
        self.assertIn('Selenium Test Announcement', self.driver.page_source)

    def test_create_announcement_validation(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/announcements/')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ New Announcement')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'newAnnModal')))
        self.driver.find_element(By.CSS_SELECTOR, '#newAnnModal .btn-full').click()
        error = WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'annError')))
        self.assertIn('Course, title and content are all required', error.text)

    def test_delete_announcement(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/announcements/')
        # Create announcement
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ New Announcement')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'newAnnModal')))
        Select(self.driver.find_element(By.ID, 'annCourse')).select_by_value(str(self.course.id))
        self.driver.find_element(By.ID, 'annTitle').send_keys('To Be Deleted')
        self.driver.find_element(By.ID, 'annContent').send_keys('Delete me')
        self.driver.find_element(By.CSS_SELECTOR, '#newAnnModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'To Be Deleted')]"))
        )
        # Delete it
        delete_btn = self.driver.find_element(By.XPATH, "//div[contains(text(),'To Be Deleted')]/ancestor::div[contains(@class,'list-item')]//button[contains(.,'Delete')]")
        delete_btn.click()
        self.driver.switch_to.alert.accept()
        WebDriverWait(self.driver, 5).until(
            EC.invisibility_of_element_located((By.XPATH, "//div[contains(text(),'To Be Deleted')]"))
        )
        self.assertNotIn('To Be Deleted', self.driver.page_source)

    # ========================= FACULTY COURSES TESTS =========================
    def test_courses_page_loads(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')
        # Wait for the page title element and check its visible text
        page_title = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.page-title'))
        )
        self.assertIn('Course & CLO/PLO Management', page_title.text)
        self.assertTrue(self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Course')]").is_displayed())
        self.assertIn('CS-TEST101', self.driver.page_source)

    def test_add_course_success(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Course')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'addCourseModal')))
        self.driver.find_element(By.ID, 'cCode').send_keys('CS-NEW101')
        self.driver.find_element(By.ID, 'cName').send_keys('New Selenium Course')
        self.driver.find_element(By.ID, 'cDesc').send_keys('Description')
        self.driver.find_element(By.ID, 'cSemester').send_keys('Spring 2025')
        credits = self.driver.find_element(By.ID, 'cCredits')
        credits.clear()
        credits.send_keys('4')
        self.driver.find_element(By.CSS_SELECTOR, '#addCourseModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'CS-NEW101: New Selenium Course')]"))
        )
        self.assertIn('CS-NEW101', self.driver.page_source)

    def test_add_clo_and_quick_plo(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')
        trigger = self.driver.find_element(By.CSS_SELECTOR, '.accordion-trigger')
        trigger.click()
        time.sleep(0.5)
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add CLO')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'addCloModal')))
        self.driver.find_element(By.ID, 'quickPloDesc').send_keys('Quick PLO from Selenium')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add PLO')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'ploAddedMsg')))
        self.driver.find_element(By.ID, 'cloDesc').send_keys('Test CLO Description')
        Select(self.driver.find_element(By.ID, 'cloBloom')).select_by_visible_text('Apply (L3)')
        self.driver.find_element(By.CSS_SELECTOR, '#addCloModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Test CLO Description')]"))
        )
        self.assertIn('Test CLO Description', self.driver.page_source)

    def test_add_student_to_course(self):
        self._login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')
        trigger = self.driver.find_element(By.CSS_SELECTOR, '.accordion-trigger')
        trigger.click()
        time.sleep(0.5)
        self.driver.find_element(By.XPATH, "//button[contains(text(),'Students')]").click()
        time.sleep(0.5)
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Student')]").click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'addStudentModal')))
        self.driver.find_element(By.ID, 'studentEmail').send_keys('student@test.com')
        self.driver.find_element(By.CSS_SELECTOR, '#addStudentModal .btn-full').click()
        msg = WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'studentMsg')))
        self.assertIn('added successfully', msg.text)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'student@test.com')]"))
        )
        self.assertIn('Test Student', self.driver.page_source)

    # STUDENT DASHBOARD TESTS 


    def test_sign_out(self):
        self._login_as_faculty()
        # The "Sign Out" link contains an arrow symbol, so use partial link text
        sign_out_link = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, 'Sign Out'))
        )
        sign_out_link.click()
        WebDriverWait(self.driver, 5).until(
            lambda d: '/signin/' in d.current_url or '/' in d.current_url
        )
        self.assertNotIn('/faculty/', self.driver.current_url)



# FACULTY ASSESSMENTS TESTS

def test_assessments_course_selection(self):
    """Verify that the assessments page shows course cards and clicking opens assessment list."""
    self._login_as_faculty()
    self.driver.get(self.live_server_url + '/faculty/assignments/')
    # Should see the course card (created in setUp)
    course_card = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, f"//div[contains(text(),'{self.course.code}')]"))
    )
    self.assertTrue(course_card.is_displayed())
    # Click on the course card (the link)
    course_link = self.driver.find_element(By.XPATH, f"//a[contains(@href, 'course={self.course.id}')]")
    course_link.click()
    WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'+ Create Assessment')]"))
    )
    self.assertIn(f"course={self.course.id}", self.driver.current_url)

def test_create_assignment_assessment(self):
    """Create an assignment (auto-published) with questions and verify it appears in published list."""
    self._login_as_faculty()
    # First ensure we have at least one CLO and PLO for the course (create in setUp if missing)
    self._ensure_clo_and_plo_exist()
    # Go to assessments page and select the course
    self.driver.get(self.live_server_url + f'/faculty/assignments/?course={self.course.id}')
    # Click "Create Assessment"
    create_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'+ Create Assessment')]"))
    )
    create_btn.click()
    # Wait for modal
    modal = WebDriverWait(self.driver, 5).until(
        EC.visibility_of_element_located((By.ID, 'createModal'))
    )
    # Select type: Assignment (already default? ensure)
    type_select = Select(self.driver.find_element(By.ID, 'typeSelect'))
    type_select.select_by_value('assignment')
    # Fill title
    self.driver.find_element(By.ID, 'aTitle').send_keys('Selenium Test Assignment')
    # Fill due date (required for assignment)
    self.driver.find_element(By.ID, 'aDue').send_keys('2025-12-31')
    # Add a question
    add_q_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Question')]")
    add_q_btn.click()
    time.sleep(0.5)  # let the question card appear
    # Fill question text
    q_text = self.driver.find_element(By.CSS_SELECTOR, '.q-card .q-text')
    q_text.send_keys('What is Selenium?')
    # Set marks (default 10 is fine)
    # Map CLO and PLO (checkboxes) – assume at least one exists
    clo_checkboxes = self.driver.find_elements(By.CSS_SELECTOR, '.q-clo-list input[type="checkbox"]')
    if clo_checkboxes:
        clo_checkboxes[0].click()
    plo_checkboxes = self.driver.find_elements(By.CSS_SELECTOR, '.q-plo-list input[type="checkbox"]')
    if plo_checkboxes:
        plo_checkboxes[0].click()
    # Submit the form
    submit_btn = self.driver.find_element(By.CSS_SELECTOR, '#createModal .btn-full')
    submit_btn.click()
    # Wait for page reload and the new assessment to appear in the published list
    WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'list-title') and text()='Selenium Test Assignment']"))
    )
    self.assertIn('Selenium Test Assignment', self.driver.page_source)

def test_create_draft_assessment(self):
    """Create a quiz (saved as draft) and verify it appears in drafts section."""
    self._login_as_faculty()
    self._ensure_clo_and_plo_exist()
    self.driver.get(self.live_server_url + f'/faculty/assignments/?course={self.course.id}')
    create_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'+ Create Assessment')]"))
    )
    create_btn.click()
    WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'createModal')))
    # Select type: Quiz
    Select(self.driver.find_element(By.ID, 'typeSelect')).select_by_value('quiz')
    self.driver.find_element(By.ID, 'aTitle').send_keys('Selenium Draft Quiz')
    # Due date optional for draft
    # Add a question
    self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Question')]").click()
    time.sleep(0.5)
    q_text = self.driver.find_element(By.CSS_SELECTOR, '.q-card .q-text')
    q_text.send_keys('Draft question')
    # Map CLO/PLO if present
    clo_cb = self.driver.find_elements(By.CSS_SELECTOR, '.q-clo-list input')
    if clo_cb: clo_cb[0].click()
    plo_cb = self.driver.find_elements(By.CSS_SELECTOR, '.q-plo-list input')
    if plo_cb: plo_cb[0].click()
    # Submit
    self.driver.find_element(By.CSS_SELECTOR, '#createModal .btn-full').click()
    # Wait for draft section to show the new draft
    WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Selenium Draft Quiz')]"))
    )
    self.assertIn('Selenium Draft Quiz', self.driver.page_source)

def test_publish_draft_assessment(self):
    """Publish a draft assessment and verify it moves to published section."""
    # First create a draft (or use an existing one)
    self._login_as_faculty()
    self._ensure_clo_and_plo_exist()
    # Create a draft quiz
    self.driver.get(self.live_server_url + f'/faculty/assignments/?course={self.course.id}')
    # If there is no draft, create one (simplify: call the draft creation method via API? but we'll do UI)
    # Check if drafts exist; if not, create one using UI
    if not self.driver.find_elements(By.XPATH, "//div[contains(text(),'Selenium Draft Quiz')]"):
        create_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Create Assessment')]")
        create_btn.click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'createModal')))
        Select(self.driver.find_element(By.ID, 'typeSelect')).select_by_value('quiz')
        self.driver.find_element(By.ID, 'aTitle').send_keys('ToBePublished')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Question')]").click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, '.q-card .q-text').send_keys('Q')
        self.driver.find_element(By.CSS_SELECTOR, '#createModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'ToBePublished')]")))
    # Now find the draft's "Publish" button and click
    draft_div = self.driver.find_element(By.XPATH, "//div[contains(text(),'ToBePublished')]/ancestor::div[contains(@style,'background:#fff;border:2px solid #fcd34d')]")
    publish_btn = draft_div.find_element(By.XPATH, ".//button[contains(text(),'Publish')]")
    publish_btn.click()
    # Wait for page reload (or AJAX)
    WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'list-title') and text()='ToBePublished']"))
    )
    self.assertNotIn('ToBePublished', draft_div.text) 
    self.assertIn('ToBePublished', self.driver.page_source)  

def test_delete_assessment(self):
    """Delete an assessment and verify it disappears."""
    self._login_as_faculty()
    self.driver.get(self.live_server_url + f'/faculty/assignments/?course={self.course.id}')
   
    if not self.driver.find_elements(By.XPATH, "//div[contains(@class,'list-item')]//button[contains(text(),'Delete')]"):
        # Create a quick assignment
        create_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Create Assessment')]")
        create_btn.click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'createModal')))
        Select(self.driver.find_element(By.ID, 'typeSelect')).select_by_value('assignment')
        self.driver.find_element(By.ID, 'aTitle').send_keys('ToBeDeleted')
        self.driver.find_element(By.ID, 'aDue').send_keys('2025-12-31')
        self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add Question')]").click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, '.q-card .q-text').send_keys('Q')
        self.driver.find_element(By.CSS_SELECTOR, '#createModal .btn-full').click()
        WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'ToBeDeleted')]")))

    delete_btn = self.driver.find_element(By.XPATH, "//div[contains(@class,'list-item')]//button[contains(text(),'Delete')]")
    delete_btn.click()
    # Confirm alert
    alert = self.driver.switch_to.alert
    alert.accept()
    WebDriverWait(self.driver, 5).until(
        EC.invisibility_of_element_located((By.XPATH, "//div[contains(text(),'ToBeDeleted')]"))
    )
    self.assertNotIn('ToBeDeleted', self.driver.page_source)


def test_materials_course_selection(self):
    """Verify the materials page shows course cards and clicking opens material list."""
    self._login_as_faculty()
    self.driver.get(self.live_server_url + '/faculty/materials/')
    course_card = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, f"//div[contains(text(),'{self.course.code}')]"))
    )
    self.assertTrue(course_card.is_displayed())
    course_link = self.driver.find_element(By.XPATH, f"//a[contains(@href, 'course={self.course.id}')]")
    course_link.click()
    WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'+ Upload Material')]"))
    )
    self.assertIn(f"course={self.course.id}", self.driver.current_url)

def test_upload_study_material(self):
    """Upload a file as study material and verify it appears in the list."""
    self._login_as_faculty()
    self.driver.get(self.live_server_url + f'/faculty/materials/?course={self.course.id}')
    # Click "Upload Material"
    upload_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'+ Upload Material')]"))
    )
    upload_btn.click()
    # Wait for modal
    modal = WebDriverWait(self.driver, 5).until(
        EC.visibility_of_element_located((By.ID, 'uploadModal'))
    )
    # Fill title
    self.driver.find_element(By.ID, 'matTitle').send_keys('Test Material')
    # Create a temporary file to upload
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        tmp.write(b'This is a test file content.')
        tmp_path = tmp.name
    try:
        # Upload the file using the hidden input
        file_input = self.driver.find_element(By.ID, 'matFile')
        file_input.send_keys(tmp_path)
        # Wait for file name to appear
        WebDriverWait(self.driver, 5).until(
            EC.text_to_be_present_in_element((By.ID, 'fileNameDisplay'), '.txt')
        )
        # Submit
        self.driver.find_element(By.ID, 'uploadBtn').click()
        # Wait for page reload and material to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Test Material')]"))
        )
        self.assertIn('Test Material', self.driver.page_source)
    finally:
        os.unlink(tmp_path)

def test_delete_study_material(self):
    """Delete an uploaded material and verify it disappears."""
    self._login_as_faculty()
    self.driver.get(self.live_server_url + f'/faculty/materials/?course={self.course.id}')
    # Ensure there is at least one material (create if needed)
    if not self.driver.find_elements(By.XPATH, "//button[contains(text(),'✕')]"):
        # Upload a material first
        upload_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Upload Material')]")
        upload_btn.click()
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'uploadModal')))
        self.driver.find_element(By.ID, 'matTitle').send_keys('ToBeDeletedMat')
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b'%PDF fake')
            tmp_path = tmp.name
        try:
            self.driver.find_element(By.ID, 'matFile').send_keys(tmp_path)
            self.driver.find_element(By.ID, 'uploadBtn').click()
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'ToBeDeletedMat')]"))
            )
        finally:
            os.unlink(tmp_path)
    # Find delete button (✕) for the first material
    delete_btn = self.driver.find_element(By.XPATH, "//div[contains(@class,'list-item') or contains(@style,'display:flex')]//button[contains(text(),'✕')]")
    delete_btn.click()
    # Confirm alert
    alert = self.driver.switch_to.alert
    alert.accept()
    # Wait for removal (the element should disappear)
    WebDriverWait(self.driver, 5).until(
        EC.invisibility_of_element_located((By.XPATH, "//div[contains(text(),'ToBeDeletedMat')]"))
    )
    self.assertNotIn('ToBeDeletedMat', self.driver.page_source)

def _ensure_clo_and_plo_exist(self):
    """Create a CLO and a PLO for the test course if they don't exist."""
    from evalify_app.models import CLO, PLO, Course
    course = self.course
    if not course.clos.exists():
        # Create a dummy CLO
        CLO.objects.create(
            code='CLO1',
            description='Test CLO',
            bloom_level='Apply (L3)',
            course=course
        )
    if not PLO.objects.exists():
        PLO.objects.create(code='PLO1', description='Test PLO')

# STUDENT ASSIGNMENTS TESTS 

def _ensure_student_assessment_exists(self):
    """Create a published assignment for the test course if none exists."""
    from evalify_app.models import Assessment, Question, CLO, PLO
    if Assessment.objects.filter(course=self.course, status='published').exists():
        return
    # Ensure CLO and PLO exist 
    if not self.course.clos.exists():
        CLO.objects.create(code='CLO1', description='Test CLO', bloom_level='Apply (L3)', course=self.course)
    if not PLO.objects.exists():
        PLO.objects.create(code='PLO1', description='Test PLO')
    # Create assessment
    assessment = Assessment.objects.create(
        title='Student Test Assignment',
        assessment_type='assignment',
        course=self.course,
        total_marks=20,
        due_date='2025-12-31',
        status='published',
        created_by=self.faculty_user
    )
    # Create a question
    question = Question.objects.create(
        assessment=assessment,
        text='What is Selenium?',
        max_marks=20,
        order=1
    )
    # Map CLO and PLO if available
    clo = self.course.clos.first()
    if clo:
        question.clos.add(clo)
    plo = PLO.objects.first()
    if plo:
        question.plos.add(plo)

def test_student_view_assignments(self):
    """Student can see the assignments list and click on a course."""
    self._login_as_student()
    # Ensure there is at least one assessment
    self._ensure_student_assessment_exists()
    self.driver.get(self.live_server_url + '/student/assignments/')
    # Wait for the page title
    WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'page-title') and contains(text(),'Assignments')]"))
    )
    # Check that the assessment appears
    assessment_title = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'list-title') and text()='Student Test Assignment']"))
    )
    self.assertTrue(assessment_title.is_displayed())

def test_student_submit_assignment_with_text(self):
    """Student submits an assignment using the text answer field."""
    self._login_as_student()
    self._ensure_student_assessment_exists()
    self.driver.get(self.live_server_url + '/student/assignments/')
    # Find the "Submit" button for the assessment (the one without a submission)
    submit_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Submit')]"))
    )
    submit_btn.click()
    
    modal = WebDriverWait(self.driver, 5).until(
        EC.visibility_of_element_located((By.ID, 'submitModal'))
    )
 
    textarea = self.driver.find_element(By.ID, 'answerText')
    textarea.send_keys('This is my answer for the assignment.')
    # Submit
    submit_modal_btn = self.driver.find_element(By.ID, 'submitBtn')
    submit_modal_btn.click()
    # page reload 
    WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'tag-graded') and contains(text(),'Submitted on')]"))
    )
    self.assertIn('Submitted on', self.driver.page_source)

def test_student_submit_assignment_with_file(self):
    """Student submits an assignment by uploading a file."""
    self._login_as_student()
    self._ensure_student_assessment_exists()
    self.driver.get(self.live_server_url + '/student/assignments/')
  
    from evalify_app.models import Assessment
    
    if Assessment.objects.filter(course=self.course, status='published').exclude(submissions__student=self.student_user).exists():
   
        pass
    else:
        # Create another assessment
        new_assessment = Assessment.objects.create(
            title='File Submission Test',
            assessment_type='assignment',
            course=self.course,
            total_marks=10,
            due_date='2025-12-31',
            status='published',
            created_by=self.faculty_user
        )
        Question.objects.create(assessment=new_assessment, text='Upload file', max_marks=10, order=1)
    self.driver.refresh()
    # Find a submit button (any)
    submit_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Submit')]"))
    )
    submit_btn.click()
    WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'submitModal')))
    # Upload a temporary file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        tmp.write(b'This is a test submission file.')
        tmp_path = tmp.name
    try:
        file_input = self.driver.find_element(By.ID, 'fileInput')
        file_input.send_keys(tmp_path)
        # Optionally leave answer empty
        self.driver.find_element(By.ID, 'submitBtn').click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'tag-graded') and contains(text(),'Submitted on')]"))
        )
        self.assertIn('Submitted on', self.driver.page_source)
    finally:
        os.unlink(tmp_path)

#  STUDENT STUDY MATERIALS TESTS 

def _ensure_study_material_exists(self):
    """Upload a study material for the test course if none exists (as faculty)."""
    from evalify_app.models import StudyMaterial
    if StudyMaterial.objects.filter(course=self.course).exists():
        return
    # Login as faculty, upload a material
    self._login_as_faculty()
    self.driver.get(self.live_server_url + f'/faculty/materials/?course={self.course.id}')
  
    upload_btn = WebDriverWait(self.driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'+ Upload Material')]"))
    )
    upload_btn.click()
    WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, 'uploadModal')))
    self.driver.find_element(By.ID, 'matTitle').send_keys('Test Study Material')
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp.write(b'%PDF test content')
        tmp_path = tmp.name
    try:
        self.driver.find_element(By.ID, 'matFile').send_keys(tmp_path)
        self.driver.find_element(By.ID, 'uploadBtn').click()
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Test Study Material')]"))
        )
    finally:
        os.unlink(tmp_path)


def test_student_view_materials_course_selection(self):
    """Student can see enrolled courses and select one to view materials."""
    self._login_as_student()
    self._ensure_study_material_exists()
    self.driver.get(self.live_server_url + '/student/materials/')

    course_card = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, f"//div[contains(text(),'{self.course.code}')]"))
    )
    self.assertTrue(course_card.is_displayed())
    # Click the link
    course_link = self.driver.find_element(By.XPATH, f"//a[contains(@href, 'course={self.course.id}')]")
    course_link.click()
    WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'page-title') and contains(text(),'Study Materials')]"))
    )
    self.assertIn(f"course={self.course.id}", self.driver.current_url)

def test_student_download_material(self):
    """Student can download a study material (verify download link is present and clickable)."""
    self._login_as_student()
    self._ensure_study_material_exists()
    self.driver.get(self.live_server_url + f'/student/materials/?course={self.course.id}')
    # Wait for the material to appear
    material_title = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Test Study Material')]"))
    )
    self.assertTrue(material_title.is_displayed())
    # Find download link
    download_link = self.driver.find_element(By.XPATH, "//a[contains(text(),'Download')]")
    self.assertTrue(download_link.is_displayed())
   
    href = download_link.get_attribute('href')
    self.assertTrue(href and href.startswith('http'))
