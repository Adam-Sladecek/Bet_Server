# Web_Scraping

## Quickstart

Install dependencies for Python >3.6 :

```bash
pip install -r requirements.txt
```
populate database from Scraping_Server_V3/scrape_server:

```bash
python manage.py populate
```
run server from Scraping_Server_V3/scrape_server:

```bash
python manage.py runserver
$env:DRIVERS = 5 ; python manage.py runserver
```
create migrations running

```bash
python manage.py makemigrations
```
apply migrations running

```bash
python manage.py migrate
```

```bash
python manage.py test
```
