def learner(request):
    return {"learner": getattr(request, "learner", None)}
