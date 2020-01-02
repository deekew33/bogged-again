from django import forms

class CommentForm(forms.Form):
    name = forms.CharField(initial='Anonymous')
    email = forms.EmailField(required=False)
    comment = forms.CharField(widget=forms.Textarea)