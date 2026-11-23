from django.dispatch import Signal

# Sent inside a transaction when a guest logs into an existing account, with
# source=<guest Learner> and target=<account Learner>. Receivers move their own rows
# from source to target; the guest is deleted right after.
merge_learners = Signal()
