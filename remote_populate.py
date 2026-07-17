from client_management.models import Client
from master.models import ExpenseHead
from core.functions import get_auto_id

clients = Client.objects.filter(is_deleted=False)
print("Found", clients.count(), "clients.")
for client in clients:
    for name in ['Purchase', 'Salary']:
        if not ExpenseHead.objects.filter(company=client, name__iexact=name, is_deleted=False).exists():
            deleted_head = ExpenseHead.objects.filter(company=client, name__iexact=name, is_deleted=True).first()
            if deleted_head:
                deleted_head.is_deleted = False
                deleted_head.save()
                print('Restored', name, 'for', client.company_name)
            else:
                new_h = ExpenseHead.objects.create(company=client, name=name, auto_id=get_auto_id(ExpenseHead))
                print('Created', name, 'for', client.company_name, 'ID:', new_h.auto_id)
