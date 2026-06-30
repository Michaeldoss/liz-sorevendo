"""
usage_router.py — Endpoint de custo em tempo real da Liz Bot.
Localização: app/api/usage_router.py
Mesmo formato de resposta usado pelo Bruno, para o dashboard
central de custos conseguir consolidar os dois.
"""

from fastapi import APIRouter
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

from app.models.database import SessionLocal, UsageLog
from app.services.usage_tracker import CUSTOS_FIXOS_MENSAIS_USD

router = APIRouter()


@router.get("/api/usage-data")
def usage_data():
    db = SessionLocal()
    try:
        agora = datetime.utcnow()
        hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = agora - timedelta(days=7)
        thirty_days_ago = agora - timedelta(days=30)

        logs_hoje = db.query(UsageLog).filter(UsageLog.created_at >= hoje_inicio).all()
        logs_7d = db.query(UsageLog).filter(UsageLog.created_at >= seven_days_ago).all()
        logs_30d = db.query(UsageLog).filter(UsageLog.created_at >= thirty_days_ago).all()
        logs_mes = db.query(UsageLog).filter(UsageLog.created_at >= mes_inicio).all()

        def soma_custo(logs):
            return round(sum(l.custo_usd or 0 for l in logs), 4)

        def por_servico(logs):
            agrupado = {}
            for l in logs:
                s = l.servico or "anthropic"
                if s not in agrupado:
                    agrupado[s] = {"custo": 0.0, "chamadas": 0}
                agrupado[s]["custo"] += l.custo_usd or 0
                agrupado[s]["chamadas"] += 1
            for s in agrupado:
                agrupado[s]["custo"] = round(agrupado[s]["custo"], 4)
            return agrupado

        def por_modelo(logs):
            agrupado = {}
            for l in logs:
                if (l.servico or "anthropic") != "anthropic":
                    continue
                m = l.model or "desconhecido"
                if m not in agrupado:
                    agrupado[m] = {"custo": 0.0, "chamadas": 0, "input_tokens": 0, "output_tokens": 0}
                agrupado[m]["custo"] += l.custo_usd or 0
                agrupado[m]["chamadas"] += 1
                agrupado[m]["input_tokens"] += l.input_tokens or 0
                agrupado[m]["output_tokens"] += l.output_tokens or 0
            for m in agrupado:
                agrupado[m]["custo"] = round(agrupado[m]["custo"], 4)
            return agrupado

        gasto_por_dia = defaultdict(float)
        for l in logs_7d:
            dia = l.created_at.strftime("%d/%m")
            gasto_por_dia[dia] += (l.custo_usd or 0)

        dias_labels = []
        dias_valores = []
        for i in range(6, -1, -1):
            d = (agora - timedelta(days=i)).strftime("%d/%m")
            dias_labels.append(d)
            dias_valores.append(round(gasto_por_dia.get(d, 0), 4))

        dias_passados_mes = agora.day
        dias_no_mes = calendar.monthrange(agora.year, agora.month)[1]
        proporcao_mes = dias_passados_mes / dias_no_mes
        custo_fixo_acumulado = round(sum(CUSTOS_FIXOS_MENSAIS_USD.values()) * proporcao_mes, 4)
        custo_fixo_total_mensal = round(sum(CUSTOS_FIXOS_MENSAIS_USD.values()), 2)

        custo_variavel_mes = soma_custo(logs_mes)
        custo_total_mes = round(custo_variavel_mes + custo_fixo_acumulado, 4)

        media_diaria_7d = soma_custo(logs_7d) / 7 if logs_7d else 0
        projecao_variavel_mensal = round(media_diaria_7d * 30, 2)
        projecao_total_mensal = round(projecao_variavel_mensal + custo_fixo_total_mensal, 2)

        return {
            "hoje": {
                "custo_usd": soma_custo(logs_hoje),
                "chamadas": len(logs_hoje),
            },
            "ultimos_7_dias": {
                "custo_usd": soma_custo(logs_7d),
                "chamadas": len(logs_7d),
                "por_modelo": por_modelo(logs_7d),
            },
            "ultimos_30_dias": {
                "custo_usd": soma_custo(logs_30d),
                "chamadas": len(logs_30d),
            },
            "mes_atual": {
                "custo_variavel_usd": round(custo_variavel_mes, 4),
                "custo_fixo_acumulado_usd": custo_fixo_acumulado,
                "custo_total_usd": custo_total_mes,
            },
            "por_servico_30d": por_servico(logs_30d),
            "custos_fixos_mensais": CUSTOS_FIXOS_MENSAIS_USD,
            "grafico_diario": {
                "labels": dias_labels,
                "valores": dias_valores,
            },
            "projecao_mensal_usd": projecao_total_mensal,
            "atualizado_em": agora.strftime("%d/%m/%Y %H:%M:%S"),
        }
    finally:
        db.close()
