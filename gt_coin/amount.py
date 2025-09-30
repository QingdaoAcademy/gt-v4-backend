from gt_forum.models import PostTypeChoice

# Rewards

REGISTER = 20

INVITE = 15
INVITE_BY = 5

POST_REWARD_MOMENT = 2
POST_REWARD_ARTICLE = 3
COMMENT_REWARD = 1


def get_post_reward_amount(type: int):
    if type == PostTypeChoice.MOMENT:
        return POST_REWARD_MOMENT
    elif type == PostTypeChoice.ARTICLE:
        return POST_REWARD_ARTICLE
    raise ValueError(f"Invalid post type: {type}")


# Rates

TRANSFER_RATE = 0.9
DONATE_RATE = 0.5

# Role

ROLE_REVIEW = -10
ROLE_AVATAR = -5

ROLE_CREATE_REWARD = 15
ROLE_CHANGE_REWARD = 10

# Punish

POST_VIOLATION = -10
COMMENT_VIOLATION = -5
ROLE_VIOLATION = -10
