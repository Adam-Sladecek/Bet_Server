from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import subprocess
import json 

class Driver: 
    def __init__(self, showBrowser: bool, url: str) -> None:
        service = Service('/app/chromedriver.exe', log_output=subprocess.DEVNULL)
        # service.creation_flags = subprocess.CREATE_NO_WINDOW
        options = Options()
        arguments = ['--no-sandbox']
        if not showBrowser: 
            arguments.extend([
                '--headless=new', '--disable-gpu', '--log-level=3', '--disable-blink-features=AutomationControlled', '--disable-extensions', '--disable-popup-blocking', 
                '--disable-translate', '--dns-prefetch-disable', '--start-maximized', '--window-size=1920,1080'
            ])
        arguments.extend([
            '--show-capture=no', 'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 
            '--disable-dev-shm-usage', '--disable-software-rasterizer', '--disable-features=VizDisplayCompositor', '--mute-audio', '--remote-debugging-port=0', 
            '--disable-notifications', '--output=/dev/null', '--disable-in-process-stack-traces', '--disable-logging', '--disable-crash-reporter'
        ])

        for argument in arguments: 
            options.add_argument(argument)

        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation']) 
        prefs = {'profile.managed_default_content_settings.images': 2}
        options.add_experimental_option('prefs', prefs)
        driver = webdriver.Chrome(service= service, options = options)
        self.driver = driver
        self.driver.get(url)

    async def execute_script(self, url: str): 
        try:
            script = f"""
            var xhr = new XMLHttpRequest();
            xhr.open("GET", "{url}", false);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.onreadystatechange = function () {{
                if (xhr.readyState == 4) {{
                    if (xhr.status == 200) {{
                        window.responseData = xhr.responseText;
                    }} else {{
                        console.error("Request failed with status:", xhr.status);
                        window.responseData = null;
                    }}
                }}
            }};
            xhr.send();
            """
            self.driver.execute_script(script)
            response_data = self.driver.execute_script("return window.responseData;")

            return json.loads(response_data)
        
        except Exception as ex:
            return None 

    def close(self):
        self.driver.quit()