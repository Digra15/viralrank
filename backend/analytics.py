"""
Backend Analytics Module

Sales estimation and ad performance analysis logic.

Logika estimasi penjualan dan analisis performa iklan.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
from backend.models import Ad


def estimate_sales(ctr: float, cost: float, conversion_rate: float) -> tuple:
    """
    Estimate sales from ad spend using CTR and conversion rate.
    
    Mengestimasi penjualan dari biaya iklan menggunakan CTR dan conversion rate.
    
    Args:
        ctr: Click-through rate (0-1) / Tingkat klik-tayang
        cost: Ad spend cost / Biaya iklan
        conversion_rate: Conversion rate (0-1) / Tingkat konversi
        
    Returns:
        tuple: (estimated_sales, estimated_revenue)
    """
    # ASSUMPTION / ASUMSI:
    #   - `cost` is in IDR (Ad.currency defaults to "IDR").
    #   - Average TikTok ad CPC in ID market ~ Rp2,000 per click.
    #   - Average order value (AOV) ~ Rp150,000.
    #   Both are constants so estimates stay comparable across ads.
    #   Keduanya konstanta agar estimasi tetap dapat dibandingkan.
    AVG_CPC = 2_000.0        # Rp per click / Rp per klik
    AVG_ORDER_VALUE = 150_000.0  # Rp per order / Rp per pesanan

    ctr = max(float(ctr or 0.0), 0.0)
    conversion_rate = min(max(float(conversion_rate or 0.0), 0.0), 1.0)
    cost = max(float(cost or 0.0), 0.0)

    # Clicks = spend / CPC. High CTR signals cheap clicks, so scale CPC down
    # modestly (1.0x at 0% CTR, 0.5x at 10%+ CTR) to reflect better efficiency.
    # Klik = belanja / CPC. CTR tinggi menandakan klik lebih murah, jadi CPC
    # diskalakan turun (1.0x pada 0% CTR, 0.5x pada 10%+ CTR).
    efficiency = 1.0 - min(ctr, 0.10) * 5.0
    effective_cpc = AVG_CPC * max(efficiency, 0.5)
    estimated_clicks = cost / effective_cpc if effective_cpc > 0 else 0.0

    # Sales = clicks * conversion rate
    # Penjualan = klik * tingkat konversi
    estimated_sales = int(estimated_clicks * conversion_rate)

    # Revenue = units * average order value
    # Pendapatan = unit * nilai pesanan rata-rata
    estimated_revenue = round(estimated_sales * AVG_ORDER_VALUE, 2)

    return estimated_sales, estimated_revenue


def estimate_monthly_impressions(likes: int, ctr: float, engagement_rate: float) -> int:
    """
    Estimate monthly video impressions from engagement metrics.
    
    Mengestimasi tayangan bulanan video dari metrik engagement.
    
    Args:
        likes: Number of likes / Jumlah like
        ctr: Click-through rate (0-1) / Tingkat klik-tayang
        engagement_rate: Engagement rate (0-1) / Tingkat engagement
        
    Returns:
        int: Estimated monthly impressions / Estimasi tayangan bulanan
    """
    # MODEL / MODEL:
    #   engagement_rate = engagements / impressions  -> impressions = engagements / rate
    #   Likes are treated as ~60% of total engagements (rest = comments/shares).
    #   CTR acts as an algorithmic-reach multiplier: higher CTR correlates with
    #   wider push, so reach is boosted by up to 1.5x at high CTR.
    #   CTR berperan sebagai pengali jangkauan algoritma (maks 1.5x).
    likes = max(int(likes or 0), 0)
    rate = float(engagement_rate or 0.0)
    if rate <= 0:
        rate = 0.05  # fallback: 5% benchmark TikTok / patokan 5%

    engagements = likes / 0.6
    base_impressions = engagements / rate

    ctr_val = min(max(float(ctr or 0.0), 0.0), 1.0)
    reach_multiplier = 1.0 + ctr_val * 1.5

    return int(base_impressions * reach_multiplier)


def rank_by_opportunity(ads: List[Ad]) -> List[Dict[str, Any]]:
    """
    Rank ads by opportunity score: estimated_sales * 0.7 + estimated_revenue * 0.3
    
    Meringking iklan berdasarkan skor peluang: estimated_sales * 0.7 + estimated_revenue * 0.3
    
    Args:
        ads: List of Ad objects / Daftar objek Ad
        
    Returns:
        List[Dict]: Ranked list with opportunity scores / Daftar terperingkat dengan skor peluang
    """
    ranked = []
    
    for ad in ads:
        # Estimate sales and revenue
        estimated_sales, estimated_revenue = estimate_sales(
            ctr=ad.ctr,
            cost=ad.cost,
            conversion_rate=0.05  # Default 5% conversion rate
        )
        
        # Calculate opportunity score (weights per spec / bobot sesuai spesifikasi).
        # NOTE: revenue is in currency units (millions of IDR) while sales is a unit
        # count, so the 0.3 revenue term dominates ranking. Normalise first if you
        # need a balanced composite score.
        # CATATAN: pendapatan dalam satuan mata uang mendominasi skor; normalisasi
        # dahulu bila butuh skor gabungan yang seimbang.
        opportunity_score = (estimated_sales * 0.7) + (estimated_revenue * 0.3)
        
        ranked.append({
            "ad_id": ad.id,
            "ad_title": ad.title,
            "creator_name": ad.creator_name,
            "estimated_sales": estimated_sales,
            "estimated_revenue": estimated_revenue,
            "ctr": ad.ctr,
            "cost": ad.cost,
            "opportunity_score": opportunity_score,
            "views": ad.views,
            "likes": ad.likes
        })
    
    # Sort by opportunity score descending
    ranked.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    return ranked


def format_currency(amount: float, currency: str = "IDR") -> str:
    """
    Format a number as currency string.
    
    Memformat angka sebagai string mata uang.
    
    Args:
        amount: Numeric amount / Jumlah numerik
        currency: Currency code (IDR, USD, etc) / Kode mata uang
        
    Returns:
        str: Formatted currency string / String mata uang terformat
    """
    currencies = {
        "IDR": {"symbol": "Rp", "decimal": 0, "separator": ".", "decimal_sep": ","},
        "USD": {"symbol": "$", "decimal": 2, "separator": ",", "decimal_sep": "."},
        "EUR": {"symbol": "€", "decimal": 2, "separator": ".", "decimal_sep": ","},
        "GBP": {"symbol": "£", "decimal": 2, "separator": ",", "decimal_sep": "."},
    }
    
    config = currencies.get(currency, currencies["IDR"])
    
    # Format the number
    decimal_places = config["decimal"]
    formatted = f"{amount:,.{decimal_places}f}"
    
    # Replace thousands separator
    formatted = formatted.replace(",", config["separator"])
    
    # Add decimal separator if needed
    if config["decimal"] > 0:
        formatted = formatted.replace(".", config["decimal_sep"], 1)
    
    # Add currency symbol
    return f"{config['symbol']}{formatted}"


def industry_stats(ads: List[Ad]) -> Dict[str, Any]:
    """
    Calculate industry statistics from a list of ads.
    
    Menghitung statistik industri dari daftar iklan.
    
    Args:
        ads: List of Ad objects / Daftar objek Ad
        
    Returns:
        Dict: Statistics including top industries, avg CTR, total cost
    """
    if not ads:
        return {
            "top_industries": [],
            "avg_ctr": 0.0,
            "total_cost": 0.0,
            "total_ads": 0,
            "total_views": 0,
            "avg_engagement_rate": 0.0
        }
    
    # Aggregate by industry
    industry_data = defaultdict(lambda: {
        "cost": 0.0,
        "views": 0,
        "ctr_sum": 0.0,
        "engagement_sum": 0.0,
        "count": 0
    })
    
    total_ctr = 0.0
    total_cost = 0.0
    total_views = 0
    total_engagement = 0
    
    for ad in ads:
        industry = ad.industry or "Unknown"
        
        industry_data[industry]["cost"] += ad.cost
        industry_data[industry]["views"] += ad.views
        industry_data[industry]["ctr_sum"] += ad.ctr
        industry_data[industry]["engagement_sum"] += (ad.likes + ad.comments + ad.shares)
        industry_data[industry]["count"] += 1
        
        total_ctr += ad.ctr
        total_cost += ad.cost
        total_views += ad.views
        total_engagement += (ad.likes + ad.comments + ad.shares)
    
    # Calculate average CTR
    avg_ctr = total_ctr / len(ads) if ads else 0.0
    
    # Calculate average engagement rate
    avg_engagement_rate = total_engagement / total_views if total_views > 0 else 0.0
    
    # Get top industries by cost
    top_industries = sorted(
        [
            {
                "industry": industry,
                "cost": data["cost"],
                "avg_ctr": data["ctr_sum"] / data["count"] if data["count"] > 0 else 0,
                "total_views": data["views"],
                "ad_count": data["count"]
            }
            for industry, data in industry_data.items()
        ],
        key=lambda x: x["cost"],
        reverse=True
    )[:10]
    
    return {
        "top_industries": top_industries,
        "avg_ctr": avg_ctr,
        "total_cost": total_cost,
        "total_ads": len(ads),
        "total_views": total_views,
        "avg_engagement_rate": avg_engagement_rate
    }
