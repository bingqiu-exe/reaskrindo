import uuid
from django.db import models

class KreditProgram(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID Finance"
    )
    insured_name = models.CharField("Insured Name", max_length=1000)
    no_sertifikat = models.CharField("No. Sertifikat", max_length=50)
    inception = models.DateField()
    expiry = models.DateField()
    uy_final = models.TextField()
    dol_date = models.DateField()
    currency = models.CharField()
    claim_amount = models.DecimalField()
    quota_share = models.DecimalField()
    surplus = models.DecimalField()

    class Meta:
        verbose_name = "Kredit Program"
        verbose_name_plural = "Kredit Program"
        unique_together = ('uy')
        ordering = ['uy']

    def __str__(self):
        return f"{self.cob} ({self.uy_final})"