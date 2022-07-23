#!/bin/bash
source pastaenv/bin/activate
python3 manage.py runserver 0.0.0.0:9998
deactivate
