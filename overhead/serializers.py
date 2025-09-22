from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from .models import Overhead
from django.db.models import Sum, F
from django.db.models import Value as V, DecimalField
from sales.models import Sale, SaleItem
import calendar
from decimal import Decimal, InvalidOperation
from datetime import timedelta, date


class OverheadSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = Overhead
        fields = [
            "id",
            "overhead_type",
            "description",
            "category",
            "duration",
            "amount",
            "created_at",
            "created_by_name",
        ]


class OverheadTotalsSerializer(serializers.Serializer):
    capital_overhead_total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)
    recurring_prev_month_total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)
    recurring_current_month_total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=False)

    @staticmethod
    def calculate_totals():
        now = timezone.now().date()
        prev_month = now.month - 1 or 12
        prev_year = now.year if now.month > 1 else now.year - 1

        capital_total = Overhead.objects.filter(overhead_type="capital").aggregate(total=Sum("amount"))["total"] or 0

        def variable_total(year, month):
            total = 0
            qs = Overhead.objects.filter(overhead_type="recurring", created_at__year=year, created_at__month=month)
            for oh in qs:
                duration = oh.duration or 1
                share = oh.amount / duration
                start_month = oh.created_at.month
                start_year = oh.created_at.year
                months = [(start_year + (start_month - 1 + i)//12, (start_month - 1 + i)%12 + 1) for i in range(duration)]
                if (year, month) in months:
                    total += share
            return total

        recurring_prev = variable_total(prev_year, prev_month)
        recurring_current = variable_total(now.year, now.month)

        grand_total = Overhead.objects.aggregate(total=Sum("amount"))["total"] or 0

        return {
            "capital_overhead_total": capital_total,
            "recurring_prev_month_total": recurring_prev,
            "recurring_current_month_total": recurring_current,
            "grand_total": grand_total
        }



class OverheadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Overhead
        fields = [
            "id",
            "overhead_type",
            "description",
            "category",
            "duration",
            "amount",
        ]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "duration": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        overhead_type = attrs.get("overhead_type")
        category = attrs.get("category")
        description = attrs.get("description")
        duration = attrs.get("duration")

        # Rule: overhead_type required
        if not overhead_type:
            raise serializers.ValidationError("Overhead type is required.")

        RECURRING_CHOICES = [
            "salaries",
            "rent",
            "insurance",
            "utilities",
            "others",
        ]
        CAPITAL_CHOICES = [
            "equipment",
            "repair",
            "license",
            "marketing",
            "others",
        ]

        # Rule: Fixed overhead must pick from fixed choices
        if overhead_type == "capital":
            if category not in CAPITAL_CHOICES:
                raise serializers.ValidationError(
                    {"category": "Invalid category for capital overhead."}
                )
            if category == "others" and not description:
                raise serializers.ValidationError(
                    {"description": "Description is required when 'others' is selected."}
                )

        # Rule: Recurring overhead must pick from variable choices
        if overhead_type == "recurring":
            if category not in RECURRING_CHOICES:
                raise serializers.ValidationError(
                    {"category": "Invalid category for recurring overhead."}
                )
            if category == "others" and not description:
                raise serializers.ValidationError(
                    {"description": "Description is required when 'others' is selected."}
                )
            if not duration:
                raise serializers.ValidationError(
                    {"duration": "Duration is required for recurring overhead."}
                )
        # Rule: Amount required
        if attrs.get("amount") is None:
            raise serializers.ValidationError("Amount is required.")

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        overhead = Overhead.objects.create(
            created_by=user,
            created_by_name=(
                user.get_full_name() or user.first_name or user.username
            ) if user else None,
            **validated_data
        )
        return overhead



class DashboardSummarySerializer(serializers.Serializer):
    discount_current_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    discount_previous_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    profit_current_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    profit_previous_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    profit_all_time = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)

    top_products = serializers.ListField()
    worst_products = serializers.ListField()
    discount_trend = serializers.ListField()
    profit_trend = serializers.ListField()
    trend_labels = serializers.ListField()
    overhead_trend = serializers.ListField()
    sales_count_trend = serializers.ListField()
    items_sold_trend = serializers.ListField()

    total_sale_current_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    total_sale_previous_month = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    total_unit_sold_current = serializers.IntegerField()
    total_unit_sold_prev = serializers.IntegerField()

    @staticmethod
    def get_dashboard_data():
        now = timezone.now().date()
        current_month = now.month
        current_year = now.year
        prev_month = current_month - 1 or 12
        prev_year = current_year if current_month > 1 else current_year - 1

        # Get overhead totals
        overheads = OverheadTotalsSerializer.calculate_totals()

        # 1. Discounts
        discount_current = Sale.objects.filter(
            sale_date__year=current_year, sale_date__month=current_month
        ).aggregate(total=Sum('total_discount'))['total'] or 0

        discount_prev = Sale.objects.filter(
            sale_date__year=prev_year, sale_date__month=prev_month
        ).aggregate(total=Sum('total_discount'))['total'] or 0

        # 2. Profit
        profit_current = Sale.objects.filter(
            sale_date__year=current_year, sale_date__month=current_month
        ).aggregate(total=Sum('total_profit'))['total'] or 0
        profit_current -= overheads['recurring_current_month_total']

        profit_prev = Sale.objects.filter(
            sale_date__year=prev_year, sale_date__month=prev_month
        ).aggregate(total=Sum('total_profit'))['total'] or 0
        profit_prev -= overheads['recurring_prev_month_total']

        profit_all_time = Sale.objects.aggregate(total=Sum('total_profit'))['total'] or 0
        profit_all_time -= overheads['grand_total']

        # 3. Top & Worst Products
        # Annotate SaleItems with product metrics
        products_agg = SaleItem.objects.values(
            'product__id', 'product__name'
        ).annotate(
            quantity_sold=Sum('quantity'),
            total_vat=Sum('vat_value'),
            total_discount=Sum('discount_value'),
            total_amount=Sum('amount'),
            total_profit=Sum('profit')
        )

        # Define querysets for current and previous month sales
        current_month_sales = Sale.objects.filter(
            sale_date__year=current_year,
            sale_date__month=current_month
        )

        previous_month_sales = Sale.objects.filter(
            sale_date__year=prev_year,
            sale_date__month=prev_month
        )

        # Total Sales Revenue
        current_month_sales_revenue = current_month_sales.aggregate(total=Sum("total_amount"))["total"] or 0
        previous_month_sales_revenue = previous_month_sales.aggregate(total=Sum("total_amount"))["total"] or 0

        # Total Sales Units
        current_month_sales_units = SaleItem.objects.filter(
            sale__sale_date__year=current_year,
            sale__sale_date__month=current_month
        ).aggregate(total=Sum("quantity"))["total"] or 0

        previous_month_sales_units = SaleItem.objects.filter(
            sale__sale_date__year=prev_year,
            sale__sale_date__month=prev_month
        ).aggregate(total=Sum("quantity"))["total"] or 0



        # Sort for top 10 by quantity_sold
        top_products = sorted(products_agg, key=lambda x: x['quantity_sold'], reverse=True)[:10]
        worst_products = sorted(products_agg, key=lambda x: x['quantity_sold'])[:10]


        # 4. Discount, Profit & Overhead Trend (last 6 months)
        months_back = 6
        discount_trend = []
        profit_trend = []
        overhead_trend = []
        labels = []
        sales_count_trend = []
        items_sold_trend = []


        def variable_total(year, month):
            total = 0
            qs = Overhead.objects.filter(overhead_type="recurring")
            for oh in qs:
                duration = oh.duration or 1
                share = oh.amount / duration
                start_month = oh.created_at.month
                start_year = oh.created_at.year
                months = [
                    (start_year + (start_month - 1 + i) // 12,
                     (start_month - 1 + i) % 12 + 1)
                    for i in range(duration)
                ]
                if (year, month) in months:
                    total += share
            return total

        for i in range(months_back - 1, -1, -1):
            target_month = current_month - i
            target_year = current_year

            if target_month <= 0:  # wrap into previous year
                target_month += 12
                target_year -= 1

            month_name = calendar.month_name[target_month]
            labels.append(f"{month_name} {str(target_year)[-2:]}")

            month_sales = Sale.objects.filter(
                sale_date__year=target_year,
                sale_date__month=target_month
            )

            month_discount = month_sales.aggregate(total=Sum("total_discount"))["total"] or 0
            month_profit = month_sales.aggregate(total=Sum("total_profit"))["total"] or 0

            # recurring overhead for this month
            month_overhead = variable_total(target_year, target_month)

            # net profit = profit - recurring overhead
            net_profit = month_profit - month_overhead

            discount_trend.append(month_discount)
            profit_trend.append(net_profit)
            overhead_trend.append(month_overhead)


            # Count number of sales (transactions/orders)
            month_sales_count = month_sales.count()

            # Sum of items sold (sum of quantities in SaleItem or equivalent model)
            month_items_sold = SaleItem.objects.filter(
                sale__sale_date__year=target_year,
                sale__sale_date__month=target_month
            ).aggregate(total=Sum("quantity"))["total"] or 0



            sales_count_trend.append(month_sales_count)
            items_sold_trend.append(month_items_sold)


        return {
            "discount_current_month": discount_current,
            "discount_previous_month": discount_prev,
            "profit_current_month": profit_current,
            "profit_previous_month": profit_prev,
            "profit_all_time": profit_all_time,
            "total_sale_current_month": current_month_sales_revenue,
            "total_sale_previous_month": previous_month_sales_revenue,
            "total_unit_sold_current": current_month_sales_units,
            "total_unit_sold_prev": previous_month_sales_units,
            "top_products": top_products,
            "worst_products": worst_products,
            "discount_trend": discount_trend,
            "profit_trend": profit_trend,
            "trend_labels": labels,
            "overhead_trend": overhead_trend,
            "sales_count_trend": sales_count_trend,
            "items_sold_trend": items_sold_trend,
        }


class RevenueTrendSerializer(serializers.Serializer):
    labels = serializers.ListField()
    revenue = serializers.ListField()

    @staticmethod
    def get_revenue_data(range_param="7d"):
        now = timezone.now().date()
        labels, revenue = [], []

        if range_param == "7d":  # Last 7 days (including today)
            for i in range(6, -1, -1):
                target_date = now - timedelta(days=i)
                day_label = target_date.strftime("%a")  # Mon, Tue, etc.
                total = Sale.objects.filter(
                    sale_date__date=target_date  
                ).aggregate(total=Sum("total_amount"))["total"] or 0

                labels.append(day_label)
                revenue.append(total)

        elif range_param == "1m":  # Last FULL previous month, split into weeks
            # Find last month
            prev_month = now.month - 1 or 12
            prev_year = now.year if now.month > 1 else now.year - 1
            start_date = date(prev_year, prev_month, 1)
            last_day = calendar.monthrange(prev_year, prev_month)[1]
            end_date = date(prev_year, prev_month, last_day)

            # Split month into weeks (1-7, 8-14, 15-21, 22-end)
            week_ranges = [
                (start_date, start_date + timedelta(days=6)),
                (start_date + timedelta(days=7), start_date + timedelta(days=13)),
                (start_date + timedelta(days=14), start_date + timedelta(days=20)),
                (start_date + timedelta(days=21), end_date),
            ]

            for idx, (week_start, week_end) in enumerate(week_ranges, 1):
                total = Sale.objects.filter(
                    sale_date__date__range=(week_start, week_end)  
                ).aggregate(total=Sum("total_amount"))["total"] or 0
                labels.append(f"Week {idx}")
                revenue.append(total)

        elif range_param in ["3m", "6m", "1y"]:  # Monthly aggregation
            months_back = {"3m": 3, "6m": 6, "1y": 12}[range_param]

            for i in range(months_back - 1, -1, -1):
                target_month = now.month - i
                target_year = now.year
                if target_month <= 0:  # wrap around year
                    target_month += 12
                    target_year -= 1

                start_date = date(target_year, target_month, 1)
                if target_year == now.year and target_month == now.month:
                    # Current month, cut at today
                    end_date = now
                else:
                    last_day = calendar.monthrange(target_year, target_month)[1]
                    end_date = date(target_year, target_month, last_day)

                month_label = calendar.month_abbr[target_month]
                total = Sale.objects.filter(
                    sale_date__date__range=(start_date, end_date)  
                ).aggregate(total=Sum("total_amount"))["total"] or 0

                labels.append(month_label)
                revenue.append(total)

        return {
            "labels": labels,
            "revenue": revenue
        }



class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    quantity = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    vat_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    cost_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_value = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "vat_value",
            "discount_value",
            "amount",
            "cost_price",
            "profit",
        ]


class SaleSerializer(serializers.ModelSerializer):
    sale_date = serializers.DateTimeField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    sale_items = SaleItemSerializer(source="items", many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "reference",
            "customer",
            "sale_date",
            "total_cost",
            "total_amount",
            "total_discount",
            "total_profit",
            "total_vat",
            "sale_items",
            "payment_type",
            "staff_name",
        ]


class UpdateOverheadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Overhead
        fields = ["id", "overhead_type", "description", "category", "duration", "amount"]
        extra_kwargs = {
            "id": {"read_only": True},
            "description": {"required": False, "allow_blank": True},
            "duration": {"required": False, "allow_blank": True},
            "category": {"required": False, "allow_blank": True},
            "amount": {"required": False},
        }

    def validate(self, attrs):
        instance = self.instance  

        # Merge with current values if not provided
        data = {**{f: getattr(instance, f) for f in self.fields}, **attrs}

        overhead_type = data.get("overhead_type")
        category = data.get("category")
        description = data.get("description")
        duration = data.get("duration")
        amount = data.get("amount")

        # --- Ensure amount is Decimal ---
        if amount is not None:
            try:
                data["amount"] = Decimal(amount)
            except (InvalidOperation, TypeError):
                raise serializers.ValidationError({"amount": "Amount must be a valid decimal number."})
            if data["amount"] <= 0:
                raise serializers.ValidationError({"amount": "Amount must be greater than zero."})

        # --- Ensure duration is int ---
        if duration is not None:
            if not isinstance(duration, int):
                raise serializers.ValidationError({"duration": "Duration must be an integer."})
            if duration < 1 or duration > 12:
                raise serializers.ValidationError({"duration": "Duration must be between 1 and 12 months."})

        # CATEGORY MAPS
        recurring_cats = {"salaries", "rent", "insurance", "utilities", "others"}
        capital_cats = {"equipment", "repair", "license", "marketing", "others"}

        # Duration rule
        if overhead_type == "capital":
            data["duration"] = None 
        elif overhead_type == "recurring" and not duration:
            raise serializers.ValidationError({"duration": "Duration is required for recurring overheads."})

        # Category validation
        if overhead_type == "capital" and category not in capital_cats:
            raise serializers.ValidationError({"category": "Invalid category for capital overhead."})
        if overhead_type == "recurring" and category not in recurring_cats:
            raise serializers.ValidationError({"category": "Invalid category for recurring overhead."})

        # Description rule for "others"
        if category == "others" and instance.category != "others" and not description:
            raise serializers.ValidationError({"description": "Description is required when selecting 'others'."})

        return data

    def update(self, instance, validated_data):
        # Only update fields provided, leave others unchanged
        for attr, value in validated_data.items():
            # Special case: allow None for duration
            if attr == "duration":
                setattr(instance, attr, value)  
                continue

            # For all other fields, skip empty string or None
            if value not in ["", None]:
                setattr(instance, attr, value)
            
            from django.utils import timezone
            request = self.context.get("request")
            if request and request.user and request.user.is_authenticated:
                instance.updated_by = request.user
                instance.updated_by_name = (
                    request.user.get_full_name() or 
                    request.user.first_name or 
                    request.user.username
                )
            instance.updated_at = timezone.now()

        instance.save()
        return instance


