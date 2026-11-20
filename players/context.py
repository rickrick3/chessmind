def player(request):
    from players.views import current_player

    return {"player": current_player(request)}
