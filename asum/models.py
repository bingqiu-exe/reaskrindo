import uuid
from django.db import models

class Asum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    main_filename = models.CharField(max_length=255)
    reference_filename = models.CharField(max_length=255)
    total_rows_processed = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    class JenisSOA(models.TextChoices):
        KLAIM = 'KLAIM', 'Klaim'
        PREMI = 'PREMI', 'Premi'

    jenis_soa = models.CharField(max_length=10, choices=JenisSOA.choices, default=JenisSOA.KLAIM)
    

