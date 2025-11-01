from django.shortcuts import render

def home(request):
    context = {
        'social_networks': [
            {'name': 'VK', 'connected': True},
            {'name': 'Telegram', 'connected': True},
        ],
        'recent_posts': [],
        'stats': {
            'total_posts': 0,
            'scheduled': 0,
            'published_today': 0,
        }
    }
    return render(request, 'home.html', context)
