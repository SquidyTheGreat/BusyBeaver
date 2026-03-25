from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarintegration',
            name='event_calendar_id',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='calendarintegration',
            name='event_calendar_name',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
