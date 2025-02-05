from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import subprocess
import json 
import os

class Driver: 
    def __init__(self, showBrowser: bool, url: str) -> None:
        chromedriver_path = '/usr/local/bin/chromedriver' if os.path.exists('/usr/local/bin/chromedriver') else 'chromedriver.exe'
        service = Service(chromedriver_path)
        options = Options()

        # Basic required options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        if not showBrowser: 
            options.add_argument('--headless=new')
            options.add_argument('--window-size=1920,1080')
        
        # Additional options for stability
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-logging')
        options.add_argument(f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Experimental options
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('prefs', {
            'profile.managed_default_content_settings.images': 2
        })

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.get(url)
        except Exception as e:
            print(f"Driver initialization error: {str(e)}")
            raise

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
            print(f"Script execution error: {str(ex)}")
            return None 

    def close(self):
        try:
            self.driver.quit()
        except Exception as e:
            print(f"Driver close error: {str(e)}")