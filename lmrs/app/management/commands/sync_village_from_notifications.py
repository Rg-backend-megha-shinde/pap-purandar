from django.core.management.base import BaseCommand
from app.models import Notification
from app.village_notification_sync import sync_village_data_from_notification


class Command(BaseCommand):
    help = "Sync all existing Notification records into VillageData records without overwriting manual data."

    def handle(self, *args, **options):
        notifications = Notification.objects.all().order_by('id')
        self.stdout.write(f"Found {notifications.count()} Notification records to process.")
        count = 0
        for notif in notifications:
            res = sync_village_data_from_notification(notif)
            if res:
                count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Synced notification ID {notif.id} for village '{notif.village}' -> VillageData ID {res.id}"
                    )
                )
            else:
                self.stdout.write(
                    f"Skipped notification ID {notif.id} for village '{notif.village}' (Already has manual data or missing location)"
                )
        self.stdout.write(self.style.SUCCESS(f"Finished sync process: {count} VillageData records populated."))
