"""
Backend Pydantic Models

Data models for TikTok Affiliate Research System.

Data structures untuk Sistem Riset Afiliasi TikTok.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Ad(BaseModel):
    """
    Represents a TikTok ad campaign item.
    
    Mewakili item kampanye iklan TikTok.
    """
    id: str = Field(description="Ad unique identifier / ID unik iklan")
    video_id: str = Field(description="TikTok video ID")
    creator_id: str = Field(description="Creator/merchant ID")
    creator_name: str = Field(description="Creator/merchant name / Nama pembuat/pedagang")
    title: str = Field(description="Ad title / Judul iklan")
    description: str = Field(description="Ad description / Deskripsi iklan")
    thumbnail_url: str = Field(description="Ad thumbnail URL")
    likes: int = Field(description="Number of likes / Jumlah like")
    comments: int = Field(description="Number of comments / Jumlah komentar")
    shares: int = Field(description="Number of shares / Jumlah share")
    views: int = Field(description="Number of views / Jumlah tayangan")
    ctr: float = Field(description="Click-through rate (0-1) / Tingkat klik-tayang")
    cost: float = Field(description="Ad spend / Biaya iklan")
    currency: str = Field(default="IDR", description="Currency code / Kode mata uang")
    created_at: datetime = Field(description="Ad creation timestamp / Waktu pembuatan iklan")
    category: Optional[str] = Field(default=None, description="Product category / Kategori produk")
    industry: Optional[str] = Field(default=None, description="Industry sector / Sektor industri")


class Product(BaseModel):
    """
    Represents a product being advertised.
    
    Mewakili produk yang diiklankan.
    """
    id: str = Field(description="Product ID / ID produk")
    ad_id: str = Field(description="Associated ad ID / ID iklan terkait")
    name: str = Field(description="Product name / Nama produk")
    price: float = Field(description="Product price / Harga produk")
    currency: str = Field(default="IDR", description="Currency code / Kode mata uang")
    category: str = Field(description="Product category / Kategori produk")
    brand: Optional[str] = Field(default=None, description="Product brand / Merek produk")
    affiliate_commission_rate: float = Field(description="Commission rate (0-1) / Tingkat komisi")
    stock: Optional[int] = Field(default=None, description="Available stock / Stok tersedia")
    link: Optional[str] = Field(default=None, description="Product link / Link produk")


class Campaign(BaseModel):
    """
    Represents a marketing campaign.
    
    Mewakili kampanye pemasaran.
    """
    id: str = Field(description="Campaign ID / ID kampanye")
    name: str = Field(description="Campaign name / Nama kampanye")
    status: str = Field(description="Campaign status: active/paused/draft / Status: aktif/ditunda/draf")
    start_date: datetime = Field(description="Campaign start date / Tanggal mulai")
    end_date: Optional[datetime] = Field(default=None, description="Campaign end date / Tanggal berakhir")
    budget_total: float = Field(description="Total budget / Anggaran total")
    budget_spent: float = Field(default=0, description="Budget spent / Anggaran terpakai")
    objective: str = Field(description="Campaign objective: sales/traffic/engagement / Tujuan: penjualan/traffic/engagement")
    ads: List[Ad] = Field(default_factory=list, description="List of ads in campaign / Daftar iklan dalam kampanye")


class SalesEstimate(BaseModel):
    """
    Estimated sales metrics from ad performance.
    
    Metrik penjualan yang diperkirakan dari performa iklan.
    """
    ad_id: str = Field(description="Ad ID / ID iklan")
    estimated_sales: int = Field(description="Estimated units sold / Estimasi unit terjual")
    estimated_revenue: float = Field(description="Estimated revenue / Estimasi pendapatan")
    estimated_commission: float = Field(description="Estimated commission / Estimasi komisi")
    confidence_score: float = Field(description="Estimation confidence (0-1) / Skor kepercayaan")
    calculation_date: datetime = Field(default_factory=datetime.utcnow, description="When estimate was calculated / Waktu estimasi dihitung")


class AnalysisRequest(BaseModel):
    """
    Request payload for ad analytics analysis.
    
    Payload permintaan untuk analisis analitik iklan.
    """
    ad_ids: Optional[List[str]] = Field(default=None, description="Specific ad IDs to analyze / ID iklan spesifik")
    category: Optional[str] = Field(default=None, description="Filter by category / Filter berdasarkan kategori")
    industry: Optional[str] = Field(default=None, description="Filter by industry / Filter berdasarkan industri")
    date_start: Optional[datetime] = Field(default=None, description="Start date for analysis / Tanggal mulai")
    date_end: Optional[datetime] = Field(default=None, description="End date for analysis / Tanggal berakhir")
    min_views: Optional[int] = Field(default=0, description="Minimum views filter / Filter tayangan minimum")
    max_ctr: Optional[float] = Field(default=1.0, description="Maximum CTR filter / Filter CTR maksimum")
    currency: str = Field(default="IDR", description="Currency for reports / Mata uang laporan")


class AnalysisResponse(BaseModel):
    """
    Response payload from ad analytics analysis.
    
    Payload respons dari analisis analitik iklan.
    """
    summary: Dict[str, Any] = Field(description="Overall summary statistics / Statistik ringkasan")
    top_ads: List[Ad] = Field(description="Top performing ads / Iklan terbaik")
    opportunity_rankings: List[Dict[str, Any]] = Field(description="Opportunity rankings / Peringkat peluang")
    industry_breakdown: Dict[str, Any] = Field(description="Stats by industry / Statistik per industri")
    currency: str = Field(default="IDR", description="Report currency / Mata uang laporan")
    generated_at: datetime = Field(description="Response timestamp / Waktu respons")
