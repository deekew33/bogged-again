from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from .models import Blog, Comment
from .forms import CommentForm
from django.utils import timezone

def allblogs(request):
    blogs = Blog.objects.order_by('-id')
    print(Blog.objects)
    return render(request, 'blog/allblogs.html', {'blogs': blogs})


def detail(request, blog_id):
    blogdetail = get_object_or_404(Blog, pk=blog_id)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = CommentForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            now = timezone.now()
            print(form.cleaned_data)
            c = Comment.objects.create(name=form.cleaned_data['name'], email=form.cleaned_data['email'],
                                   comment=form.cleaned_data['comment'],blog_id=blog_id, pub_time=now)
            c.save()
            # redirect to a new URL:
            return HttpResponseRedirect('/blog/')

        # if a GET (or any other method) we'll create a blank form
    else:
        form = CommentForm()
    #get all comments for a certain blog id
    comments = Comment.objects.filter(blog_id=blog_id)
    blogdetail.paragraphs=blogdetail.body.split('\r\n')
    return render(request, 'blog/detail.html', {'blog': blogdetail,'form':form,'comments':comments,'blog_id':blog_id})