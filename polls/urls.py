from django.urls import path

from . import views

app_name = 'polls'
urlpatterns = [
    path('',                views.index,          name='index'),
    path('analyzenews/',    views.analyzenews,    name='analyzenews'),
    path('dailybog/',       views.dailybog,       name='dailybog'),
    path('bogchives/',      views.bogchives,      name='bogchives'),
    path('selectbogchive/', views.selectbogchive, name='selectbogchive')
]
