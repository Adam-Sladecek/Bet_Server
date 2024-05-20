def getCommonDriver(showBrowser):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    service = Service('chromedriver.exe')
    options = Options()
    if not showBrowser: 
        options.add_argument("--headless")
    options.add_argument('log-level=3')   
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service= service, options = options)