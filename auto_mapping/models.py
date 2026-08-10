from django.db import models

class AutoMapping(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    main_file_name = models.CharField(max_length=255)
    reference_file_name = models.CharField(max_length=255, blank=True, null=True)
    total_rows = models.IntegerField(default=0)
    unmapped_cob_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Batch {self.id} - {self.main_file_name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"