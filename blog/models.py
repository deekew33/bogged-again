from django.db import models

class Blog(models.Model):
    title = models.CharField(max_length=255)
    pub_date = models.DateTimeField()
    image = models.ImageField(upload_to='images')
    body = models.TextField()

    def summary(self):
        return self.body[:100]

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e, %Y')

    def __str__(self):
        return self.title


class Comment(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(default="not@real.email")
    comment = models.TextField()
    blog_id = models.IntegerField()
    pub_time = models.DateTimeField()

    def pub_date_pretty(self):
        return self.pub_time.strftime('%H:%M, %b %e %Y')