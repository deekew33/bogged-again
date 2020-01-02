import datetime

from django.db import models
from django.utils import timezone


class Ticker(models.Model):
    pub_time = models.DateTimeField()
    file = models.FileField(upload_to='files/')