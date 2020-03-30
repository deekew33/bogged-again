from django.urls import path

from . import views

app_name = 'polls'
urlpatterns = [
    path('',           views.index,     name='index'),
    path('bogging/',   views.bogging,   name='boggers'),
    path('dailybog/',  views.dailybog,  name='bogged'),
    path('entrance/',  views.entrance,  name='entrance'),
    path('bogchives/', views.bogchives, name='bogchives')
]
