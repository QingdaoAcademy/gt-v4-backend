from django.db import models


class ReviewStatusChoice(models.IntegerChoices):
    REJECTED = -3, "Rejected"
    PENDING_RECHECK = -2, "Pending recheck"
    PENDING = -1, "Pending"
    NO_NEED = 0, "No need"
    ACCEPTED = 1, "Accepted"
