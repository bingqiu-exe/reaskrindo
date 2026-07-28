from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
import json

from finance.models import Finance
from services.finance_services import FinanceServices

@csrf_exempt
@require_http_methods(["POST"])
def process_and_export_asum(request):
    if 'main_file' not in request.FILES or 'reference_file' not in request.FILES:
        return JsonResponse({
            'error': 'Both "main_file" and "reference_file" must be uploaded.'
        }, status=400)

    main_file = request.FILES['main_file']
    reference_file = request.FILES['reference_file']

    jenis_soa = request.POST.get('jenis_soa', request.GET.get('jenis_soa', Finance.JenisSOA.KLAIM)).upper()
    export_format = request.GET.get('export_format', 'excel').lower()

    try:
        if jenis_soa == Finance.JenisSOA.PREMI:
            result_df = FinanceServices.process_finance_allocation_premi(main_file, reference_file)
        else:
            result_df = FinanceServices.process_finance_allocation_claim(main_file, reference_file)

        Finance.objects.create(
            main_filename=main_file.name,
            reference_filename=reference_file.name,
            total_rows_processed=len(result_df),
            jenis_soa=jenis_soa
        )

        if export_format == 'excel':
            excel_bytes = FinanceServices.export_to_excel(result_df)
            response = HttpResponse(
                excel_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="finance_spreading_{jenis_soa.lower()}_result.xlsx"'
            return response

        elif export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="finance_spreadin_{jenis_soa.lower()}_result.csv"'
            result_df.to_csv(path_or_buf=response, index=False)
            return response

        else:
            json_records = json.loads(result_df.to_json(orient='records', date_format='iso'))
            return JsonResponse({
                'message': 'Data processed successfully.',
                'jenis_soa': jenis_soa,
                'total_rows': len(result_df),
                'results': json_records
            }, status=200)

    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)