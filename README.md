[![PyPI version](https://badge.fury.io/py/django-inspectdb-refactor.svg)](https://badge.fury.io/py/django-inspectdb-refactor)

Django Inspectdb Refactor
========================
A simple utility command based on django inspectdb management command.

Overview:
---------

Django's ``inspectb`` command prepares database models classes based on existing database.
    This is very handy tool, in case we have to work on some already existing database.
    
   It outputs the classes to standard output, which can be pipelined to a python file.
    
 But when you have a large database, containing hundreds of tables, the models file becomes too large. It is better to write ``separate model file for each table`` and keep that under models folder inside the app directory. Django will get the model classes from the ``init`` file you write inside the models folder.
 Same holds for admin, views and forms.
    
 Django Inspectdb Refactor will automatically create the required folders and create separate python files for each model.
    

Requirements:
-----------
Requires Django version >= 1.9

Installation:
------------
You can install it via pip or to get the latest version clone this repo.

`
pip install django-inspectdb-refactor 
`

Add ``inspectdb_refactor`` to your ``INSTALLED_APPS`` inside settings.py of your project.

Usage:
-----
 The command accepts two command line arguments:
  
  - ``app`` : This is a required argument. You need to provide app_label in order to 
          make models in that particular app.
  - ``database``: To specify a particular database. Otherwise picks default from settings.
  
  For example, If you have an app called ``products`` and database ``product_db`` then
  
  `
  python manage.py inspectdb_refactor --database=product_db --app=products
  `

Upgrading:
---------

See [CHANGELOG](https://github.com/farhan0581/django-inspectdb-refactor/blob/master/CHANGELOG.md)

For Django versions less then 2.1 use v0.3 using `pip install django-inspectdb-refactor==0.3`


License:
--------
Django Inspectdb Refactor is an Open Source project licensed under the terms of the BSD3 license.
