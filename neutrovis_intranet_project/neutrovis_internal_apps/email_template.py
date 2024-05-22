def notification_approval_sc(record: str, approval: str, link: str) -> str:
    return f"The claim ({record}) is approved by {approval}.\nYou can view the record here: {link}"


def notification_verified_sc(record: str, approval: str, link: str) -> str:
    return f"The claim ({record}) is verified by {approval}.\nYou can view the record here: {link}"


def notification_reject_sc(record: str, approval: str, reason: str, link: str) -> str:
    clean_reason = reason[0].lower() + reason[1:]
    return f"The claim {record} is rejected by {approval} due to {clean_reason}.\nYou can view the record here: {link}"


def notification_submission_sc(record: str, requestor: str, link: str) -> str:
    return f"{requestor} has submitted a claim ({record}) for approval.\nYou can view the record here: {link}"


def notification_submission_tr(record: str, requestor: str, link: str) -> str:
    return (f"{requestor} has submitted a Travel Request ({record}) for your approval.\n"
            f"You can view the request here: {link}")


def notification_reject_tr(record: str, approval: str, reason: str, link: str) -> str:
    clean_reason = reason[0].lower() + reason[1:]
    return (f"The request {record} is rejected by {approval} due to {clean_reason}.\n"
            f"You can view the request here: {link}")


def notification_approval_tr(record: str, approval: str, link: str) -> str:
    return (f"The request ({record}) is approved by {approval}.\n"
            f"You can view the request here: {link}")


def password_reset_email(link: str, user: str) -> str:
    return (f"Dear {user},\n"
            f"Here is the password reset link: {link} for Neutrovis Intranet Portal.\n"
            f"Do not share this link with other person!")
