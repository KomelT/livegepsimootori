from allauth.account.models import EmailAddress
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils.timezone import now

from routechoices.core.models import Club

START_PROCESS = parse("2025-05-24T00:00:00Z")


class Command(BaseCommand):
    help = "Remove club without activity"

    def add_arguments(self, parser):
        parser.add_argument("-d", "--date", type=str, required=False)

    def send_warning(self, days, club):
        print(f"- {club.name} -> {days} warning")
        admins = club.admins.all().values_list("id", flat=True)
        if not admins:
            print("  No admins to send emails to\n")
            return
        to_emails = list(
            EmailAddress.objects.filter(
                user_id__in=admins, verified=True, primary=True
            ).values_list("email", flat=True)
        )
        print(f"  Sending Email to {", ".join(to_emails)}\n")
        msg = EmailMessage(
            f'[Track.meshtrail.si] ACTION REQUIRED, Your club "{club.name}" may get deleted in {days}',
            f"""Hi,

We've noticed you haven't signed in to your Track.meshtrail.si account in a while. In fact it's been more than a year! We routinely remove inactive accounts to ensure we're not storing any data you don't want us to.

This email is to let you know that in {days} time we'll be deleting your inactive Track.meshtrail.si club "{club.name}", along with any data in your club (such as your maps and events).

It's super simple to stop this from happening. Just sign in!

https://www.track.meshtrail.si/login
""",
            settings.DEFAULT_FROM_EMAIL,
            list(to_emails),
        )
        msg.send()

    def delete_club(self, club):
        print(f"- {club.name} -> DELETING NOW")
        admins = club.admins.all().values_list("id", flat=True)
        if not admins:
            print("  No admins to send emails to\n")
        else:
            to_emails = list(
                EmailAddress.objects.filter(
                    user_id__in=admins, verified=True, primary=True
                ).values_list("email", flat=True)
            )
            print(f"  Sending Email to {", ".join(to_emails)}\n")
            msg = EmailMessage(
                f'[Track.meshtrail.si] Your club "{club.name}" has been deleted',
                f"""Hi,

We've noticed you haven't signed in to your Track.meshtrail.si account in a while. In fact it's been more than a year! We routinely remove inactive accounts to ensure we're not storing any data you don't want us to.

This email is to let you know that we have now deleted your inactive Track.meshtrail.si club "{club.name}", along with any data in your club (such as your maps and events).
""",
                settings.DEFAULT_FROM_EMAIL,
                list(to_emails),
            )
            msg.send()
        club.delete()

    def handle(self, *args, **options):
        asked_date = options.get("date")
        if asked_date:
            try:
                nyt = parse(asked_date)
            except Exception:
                self.stderr.write("Invalid date")
                return
        else:
            nyt = now()

        nyt = nyt.replace(hour=0, minute=0, second=0, microsecond=0)
        today = nyt.date()
        tomorrow = (nyt + relativedelta(days=1)).date()
        seven_days_from_now = (nyt + relativedelta(days=7)).date()
        thirty_days_from_now = (nyt + relativedelta(days=30)).date()

        thirthy_days_warning_count = 0
        seven_days_warning_count = 0
        twenty_four_hours_warning_count = 0
        deleted_count = 0

        clubs = (
            Club.objects.annotate(last_login=Max("admins__last_login"))
            .filter(
                upgraded=False,
                frontpage_featured=False,
            )
            .order_by("last_login")
        )
        for club in clubs:
            if club.last_login is None:
                club.last_login = club.creation_date
            due_deletion = max(
                START_PROCESS + relativedelta(days=30),
                club.last_login + relativedelta(years=1, days=30),
            ).date()
            if due_deletion == today:
                self.delete_club(club)
                deleted_count += 1
            elif due_deletion == tomorrow:
                self.send_warning("24 hours", club)
                twenty_four_hours_warning_count += 1
            elif due_deletion == seven_days_from_now:
                self.send_warning("7 days", club)
                seven_days_warning_count += 1
            elif due_deletion == thirty_days_from_now:
                self.send_warning("30 days", club)
                thirthy_days_warning_count += 1

        self.stdout.write(
            f"30 days to deletion warning sent: {thirthy_days_warning_count}"
        )
        self.stdout.write(
            f"7 days to deletion warning sent: {seven_days_warning_count}"
        )
        self.stdout.write(
            f"24 hours to deletion warning sent: {twenty_four_hours_warning_count}"
        )
        self.stdout.write(f"Clubs deleted: {deleted_count}")
