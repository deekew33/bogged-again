from django.contrib import admin
from django.urls import include, path
from blog import views
from django.conf.urls.static import static
from django.conf import settings
import blog

urlpatterns = [
    path('polls/', include('polls.urls')),
    path('admin/', admin.site.urls),
    path('blog/', views.allblogs, name='allblogs'),
    path('blog/<int:blog_id>/', views.detail, name="detail"),
] + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)