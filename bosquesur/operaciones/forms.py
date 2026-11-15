import re
from decimal import Decimal

from django import forms

from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega
from operaciones.models import GuiaDespacho, LoteCosecha, OrdenProduccion, Paquete

PATENTE_CHILENA = re.compile(r"^([A-Z]{4}\d{2}|[A-Z]{2}\d{4})$")


class FormularioBootstrap:
    """Agrega las clases CSS de Bootstrap a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxSelectMultiple):
                continue
            clase = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs.setdefault("class", clase)


class LoteCosechaForm(FormularioBootstrap, forms.Form):
    faena = forms.ModelChoiceField(queryset=Faena.objects.filter(activa=True), label="Predio / Faena")
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(tipo=Producto.Tipo.ROLLIZO, activo=True), label="Especie / Rollizo"
    )
    volumen_cosechado = forms.DecimalField(
        label="Volumen cosechado (m³)",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    cuadrilla = forms.CharField(
        label="Cuadrilla forestal", max_length=100, initial="Cuadrilla Forestal 1"
    )
    observacion = forms.CharField(
        label="Observación", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and usuario.faena_id and not usuario.is_superuser:
            self.fields["faena"].queryset = Faena.objects.filter(pk=usuario.faena_id)
            self.fields["faena"].initial = usuario.faena_id


class GuiaDespachoForm(FormularioBootstrap, forms.Form):
    faena = forms.ModelChoiceField(queryset=Faena.objects.filter(activa=True))
    lote_cosecha = forms.ModelChoiceField(
        queryset=LoteCosecha.objects.select_related("faena", "producto"),
        required=False,
        label="Lote de cosecha asociado",
    )
    patio_destino = forms.ModelChoiceField(queryset=Patio.objects.filter(activo=True), label="Patio de destino")
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(tipo=Producto.Tipo.ROLLIZO, activo=True), label="Producto (rollizo)"
    )
    volumen_enviado = forms.DecimalField(
        label="Volumen enviado (m³)", min_value=Decimal("0.001"), max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    patente_camion = forms.CharField(
        label="Patente del camión", max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "ABCD12", "autocapitalize": "characters"}),
    )
    conductor = forms.CharField(max_length=100)

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un encargado de faena solo emite desde su propia faena.
        if usuario is not None and usuario.faena_id and not usuario.is_superuser:
            self.fields["faena"].queryset = Faena.objects.filter(pk=usuario.faena_id)
            self.fields["faena"].initial = usuario.faena_id
            self.fields["lote_cosecha"].queryset = LoteCosecha.objects.filter(faena_id=usuario.faena_id)

    def clean_patente_camion(self):
        patente = re.sub(r"[\s\-·.]", "", self.cleaned_data["patente_camion"].upper())
        if not PATENTE_CHILENA.match(patente):
            raise forms.ValidationError("Formato de patente no válido (ej.: ABCD12 o AB1234).")
        return patente


class RecepcionForm(FormularioBootstrap, forms.Form):
    volumen_recibido = forms.DecimalField(
        label="Volumen recibido en patio (m³)", min_value=Decimal("0.001"), max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal", "autofocus": True}),
    )
    observacion = forms.CharField(
        label="Observación", required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ej.: rollizos con daño, carga mal estibada…"}),
    )


class OrdenProduccionForm(FormularioBootstrap, forms.Form):
    patio = forms.ModelChoiceField(queryset=Patio.objects.filter(activo=True))
    guia_origen = forms.ModelChoiceField(
        queryset=GuiaDespacho.objects.filter(estado=GuiaDespacho.Estado.RECEPCIONADA).select_related("faena"),
        required=False,
        label="Guía de origen (trazabilidad directa)",
    )
    producto_entrada = forms.ModelChoiceField(
        queryset=Producto.objects.filter(tipo=Producto.Tipo.ROLLIZO, activo=True), label="Rollizo consumido"
    )
    volumen_entrada = forms.DecimalField(
        label="Volumen consumido (m³)", min_value=Decimal("0.001"), max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001"}),
    )
    producto_salida = forms.ModelChoiceField(
        queryset=Producto.objects.filter(tipo=Producto.Tipo.ASERRADO, activo=True), label="Madera producida"
    )
    volumen_salida = forms.DecimalField(
        label="Volumen producido (m³)", min_value=Decimal("0.001"), max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001"}),
    )
    observacion = forms.CharField(label="Observación", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and usuario.patio_id and not usuario.is_superuser:
            self.fields["patio"].queryset = Patio.objects.filter(pk=usuario.patio_id)
            self.fields["patio"].initial = usuario.patio_id
            self.fields["guia_origen"].queryset = GuiaDespacho.objects.filter(
                estado=GuiaDespacho.Estado.RECEPCIONADA, patio_destino_id=usuario.patio_id
            )

    def clean(self):
        datos = super().clean()
        entrada, salida = datos.get("volumen_entrada"), datos.get("volumen_salida")
        if entrada and salida and salida > entrada:
            self.add_error("volumen_salida", "No puede superar el volumen de rollizo consumido.")
        return datos


class PaqueteForm(FormularioBootstrap, forms.Form):
    orden_produccion = forms.ModelChoiceField(
        queryset=OrdenProduccion.objects.select_related("patio", "producto_salida"),
        label="Orden de producción origen",
    )
    ubicacion = forms.ModelChoiceField(
        queryset=UbicacionBodega.objects.filter(activa=True).select_related("patio"),
        label="Ubicación inicial en bodega",
    )
    volumen_m3 = forms.DecimalField(
        label="Volumen del paquete (m³)",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    piezas = forms.IntegerField(label="Cantidad de piezas/tablas", min_value=1, initial=120)
    calidad = forms.ChoiceField(choices=Paquete.Calidad.choices, initial=Paquete.Calidad.GRADO_A)
    observacion = forms.CharField(
        label="Observación", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and usuario.patio_id and not usuario.is_superuser:
            self.fields["orden_produccion"].queryset = OrdenProduccion.objects.filter(
                patio_id=usuario.patio_id
            ).select_related("patio", "producto_salida")
            self.fields["ubicacion"].queryset = UbicacionBodega.objects.filter(
                activa=True, patio_id=usuario.patio_id
            ).select_related("patio")


class ProcesoPaqueteForm(FormularioBootstrap, forms.Form):
    PROCESOS = [c for c in Paquete.Proceso.choices if c[0] != Paquete.Proceso.NINGUNO]
    proceso = forms.ChoiceField(choices=PROCESOS, label="Proceso posterior a aplicar")
    ubicacion_destino = forms.ModelChoiceField(
        queryset=UbicacionBodega.objects.filter(activa=True).select_related("patio"),
        required=False,
        label="Mover a ubicación (opcional)",
    )
    calidad_resultante = forms.ChoiceField(
        choices=[("", "Mantener calidad actual")] + list(Paquete.Calidad.choices),
        required=False,
        label="Calidad resultante",
    )
    merma_m3 = forms.DecimalField(
        label="Merma del proceso (m³)",
        min_value=Decimal("0"),
        max_digits=10,
        decimal_places=3,
        initial=Decimal("0.000"),
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    observacion = forms.CharField(
        label="Observación técnica", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class MovimientoPaqueteForm(FormularioBootstrap, forms.Form):
    ubicacion_destino = forms.ModelChoiceField(
        queryset=UbicacionBodega.objects.filter(activa=True).select_related("patio"),
        label="Nueva ubicación en bodega",
    )
    observacion = forms.CharField(
        label="Motivo del traslado", required=False, widget=forms.TextInput(attrs={"placeholder": "Ej.: paso a bodega despacho"})
    )


class OrdenCompraForm(FormularioBootstrap, forms.Form):
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True), label="Proveedor externo"
    )
    patio_destino = forms.ModelChoiceField(
        queryset=Patio.objects.filter(activo=True), label="Patio de recepción"
    )
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True), label="Producto o insumo"
    )
    cantidad = forms.DecimalField(
        label="Cantidad solicitada",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    precio_unitario_clp = forms.IntegerField(
        label="Precio unitario ($ CLP)", min_value=1, initial=45000
    )
    observacion = forms.CharField(
        label="Justificación / detalle", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class RecepcionCompraForm(FormularioBootstrap, forms.Form):
    cantidad_recibida = forms.DecimalField(
        label="Cantidad recepcionada conforme",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "inputmode": "decimal"}),
    )
    observacion = forms.CharField(
        label="Observación de bodega", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class PedidoVentaForm(FormularioBootstrap, forms.Form):
    cliente = forms.ModelChoiceField(queryset=Cliente.objects.filter(activo=True), label="Cliente comercial")
    patio_despacho = forms.ModelChoiceField(
        queryset=Patio.objects.filter(activo=True), label="Patio de despacho"
    )
    paquetes = forms.ModelMultipleChoiceField(
        queryset=Paquete.objects.filter(
            estado__in=[Paquete.Estado.ELABORADO, Paquete.Estado.PROCESADO]
        ).select_related("producto", "ubicacion", "ubicacion__patio"),
        widget=forms.CheckboxSelectMultiple,
        label="Paquetes QR disponibles para reservar",
    )
    precio_m3_clp = forms.IntegerField(
        label="Precio promedio por m³ ($ CLP)", min_value=1000, initial=185000
    )
    observacion = forms.CharField(
        label="Notas comerciales", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class DespachoVentaForm(FormularioBootstrap, forms.Form):
    patente_camion = forms.CharField(
        label="Patente del transporte", max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "ABCD12", "autocapitalize": "characters"}),
    )
    conductor = forms.CharField(label="Nombre del conductor", max_length=100)
    observacion = forms.CharField(
        label="Observación de despacho", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def clean_patente_camion(self):
        patente = re.sub(r"[\s\-·.]", "", self.cleaned_data["patente_camion"].upper())
        if not PATENTE_CHILENA.match(patente):
            raise forms.ValidationError("Formato de patente no válido (ej.: ABCD12 o AB1234).")
        return patente
