import os
import sys
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from django.test import LiveServerTestCase
from django.conf import settings
from selenium import webdriver

RUN_LOCAL = ('SAUCE_USERNAME' not in os.environ)
"""
For a long time, we used SauceLabs for CI testing, because they provide free
browser VMs for Open Source projects. However, more tests failed because of
connection timeouts to SauceLabs than for real reasons, so we're using
PhantomJS now. However, we'll keep the SauceClient code here as it might prove
useful some day.
"""

if RUN_LOCAL:
    # could add Chrome, Firefox, etc... here
    BROWSERS = [os.environ.get('TEST_BROWSER', 'PhantomJS')]
else:
    from sauceclient import SauceClient
    USERNAME = os.environ.get('SAUCE_USERNAME')
    ACCESS_KEY = os.environ.get('SAUCE_ACCESS_KEY')
    sauce = SauceClient(USERNAME, ACCESS_KEY)

    BROWSERS = [
        {"platform": "Mac OS X 10.9",
         "browserName": "chrome",
         "version": "35"},
        {"platform": "Windows 8.1",
         "browserName": "internet explorer",
         "version": "11"},
        {"platform": "Linux",
         "browserName": "firefox",
         "version": "29"}]


def on_platforms():
    if RUN_LOCAL:
        def decorator(base_class):
            module = sys.modules[base_class.__module__].__dict__
            for i, platform in enumerate(BROWSERS):
                d = dict(base_class.__dict__)
                d['browser'] = platform
                name = "%s_%s" % (base_class.__name__, i + 1)
                module[name] = type(name, (base_class,), d)
            pass
        return decorator

    def decorator(base_class):
        module = sys.modules[base_class.__module__].__dict__
        for i, platform in enumerate(BROWSERS):
            d = dict(base_class.__dict__)
            d['desired_capabilities'] = platform
            name = "%s_%s" % (base_class.__name__, i + 1)
            module[name] = type(name, (base_class,), d)
    return decorator


class BrowserTest(StaticLiveServerTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings.DEBUG = ('--debug' in sys.argv)

    def setUp(self):
        if RUN_LOCAL:
            self.setUpLocal()
        else:
            self.setUpSauce()

    def tearDown(self):
        if RUN_LOCAL:
            self.tearDownLocal()
        else:
            self.tearDownSauce()

    def setUpSauce(self):
        if 'TRAVIS_JOB_NUMBER' in os.environ:
            self.desired_capabilities['tunnel-identifier'] = \
                os.environ['TRAVIS_JOB_NUMBER']
            self.desired_capabilities['build'] = os.environ['TRAVIS_BUILD_NUMBER']
            self.desired_capabilities['tags'] = \
                [os.environ['TRAVIS_PYTHON_VERSION'], 'CI']
        self.desired_capabilities['name'] = self.id()

        sauce_url = "http://%s:%s@ondemand.saucelabs.com:80/wd/hub"
        self.driver = webdriver.Remote(
            desired_capabilities=self.desired_capabilities,
            command_executor=sauce_url % (USERNAME, ACCESS_KEY)
        )
        self.driver.implicitly_wait(5)

    def setUpLocal(self):
        self.driver = getattr(webdriver, self.browser)()
        self.driver.implicitly_wait(3)

    def tearDownLocal(self):
        self.driver.quit()

    def tearDownSauce(self):
        print("\nLink to your job: \n "
              "https://saucelabs.com/jobs/%s \n" % self.driver.session_id)
        try:
            if sys.exc_info() == (None, None, None):
                sauce.jobs.update_job(self.driver.session_id, passed=True)
            else:
                sauce.jobs.update_job(self.driver.session_id, passed=False)
        finally:
            self.driver.quit()
