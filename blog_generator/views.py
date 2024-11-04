from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from pytubefix import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from .models import BlogPost
import json
import os

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # get yt title
        video_title, video_id = yt_info(yt_link)

        # get transcript
        transcript = get_transcription(video_id)

        # use openai to generate the blog
        blog_content = generate_blog_from_transcription(transcript)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user = request.user,
            youtube_title = video_title,
            youtube_link = yt_link,
            generated_content = blog_content,
        )
        new_blog_article.save()
        # Return blog article as response

        return JsonResponse({'content': blog_content})

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_info(link):
    '''Returns title of yt video'''
    yt = YouTube(link)
    title = yt.title
    video_id = yt.video_id
    return title, video_id

def get_transcription(video_id):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    text = ''
    for i in transcript:
        text_i = i['text']
        if isinstance(text_i, str):
            text = text + ' ' + text_i
    return text

def generate_blog_from_transcription(transcription):

    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

    genai.configure(api_key=GOOGLE_API_KEY)

    config = genai.GenerationConfig(
        max_output_tokens=1024,
    )

    model = genai.GenerativeModel(
        model_name = 'gemini-1.5-flash',
        generation_config = config
    )

    prompt = f"Based on the following transcript from a YouTube video, write a summary blog article using no more than 300 words explaining what the video is about (avoid using any formatting character):\n\n{transcription}\n\nArticle:"

    generated_content = model.generate_content(prompt).text

    return generated_content

def user_login(request):

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = 'Invalid username or password'
            return render(request, 'login.html', {'error_message':error_message})
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = "Passwords do not match"
            return render(request, 'signup.html', {'error_message':error_message})

    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail':blog_article_detail})
    else:
        return redirect('/')