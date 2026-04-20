# Airline Status Documentation

This directory contains airline frequent flyer program documentation for RAG (Retrieval Augmented Generation) with AWS Bedrock Knowledge Base.

## Directory Structure

```
airline_docs/
├── pdfs/               # PDF captures of airline status pages
│   ├── united/        # United MileagePlus documents
│   ├── delta/         # Delta SkyMiles Medallion documents
│   ├── american/      # American AAdvantage documents
│   └── alaska/        # Alaska Mileage Plan documents
├── structured/        # Manually curated markdown with tier tables
└── metadata.json      # Collection metadata and source tracking
```

## Collection Process

1. **PDFs**: Manually save airline status pages as PDFs using browser Print to PDF
   - Navigate to airline status page
   - Press Cmd+P (Mac) or Ctrl+P (Windows)
   - Select "Save as PDF"
   - Save with descriptive filename: `{airline}_{topic}.pdf`

2. **Structured Data**: Create markdown files with tier requirement tables
   - Extract tier thresholds, benefits, rules
   - Format as tables for clear RAG retrieval
   - Include source URLs and last updated date

3. **Metadata**: Track sources and verification dates in `metadata.json`

## Target Airlines

- **United Airlines** - MileagePlus Premier Status
- **Delta Air Lines** - SkyMiles Medallion Status
- **American Airlines** - AAdvantage Status
- **Alaska Airlines** - Mileage Plan MVP Status

## S3 Upload

After collecting documents:
```bash
aws s3 sync pdfs/ s3://flight-record-airline-kb/policies/
aws s3 sync structured/ s3://flight-record-airline-kb/structured/
aws s3 cp metadata.json s3://flight-record-airline-kb/metadata.json
```

## Update Schedule

- **Annual**: January/February (airlines typically announce program changes)
- **As Needed**: When major program updates are announced

## Last Updated

Collection Date: January 2026
