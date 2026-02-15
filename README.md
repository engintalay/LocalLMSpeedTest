# LLM Benchmark Tool

Local LLM performans testi için interaktif Python aracı. Ollama, LM Studio ve llama.cpp gibi yerel LLM backend'lerini test eder.

## Özellikler

- **Çoklu Backend Desteği**: Ollama, LM Studio, llama.cpp
- **Hazır Prompt Koleksiyonu**: Kısa, orta, uzun ve ekstra uzun promptlar
- **Detaylı Metrikler**: Token/saniye, yanıt süresi, toplam token sayısı
- **Çoklu Test İterasyonu**: Ortalama performans hesaplama
- **Toplu Test Modu**: Tüm modelleri tek seferde test et
- **Performans Özeti**: Sonuçları hızdan yavaşa sıralı tablo
- **Interaktif Menü**: Kolay kullanım için klavye navigasyonu
- **Sonuç Kaydetme**: Test sonuçlarını otomatik kaydetme

## Kurulum

```bash
# Depoyu klonlayın
git clone <repo-url>
cd LocalLMSpeedTest

# Sanal ortam oluşturun
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows

# Bağımlılıkları yükleyin
pip install requests readchar
```

## Kullanım

```bash
python llm-benchmark.py
```

### Menü Navigasyonu

- **↑/↓**: Seçenekler arasında gezinme
- **Enter**: Seçimi onayla
- **q**: Çıkış

### Test Akışı

1. Backend seçin (Ollama/LM Studio/llama.cpp)
2. Model seçin veya "Test all models" ile tüm modelleri seçin
3. Prompt dosyası seçin veya "Test all prompts" ile tüm promptları seçin
4. Test iterasyon sayısını ayarlayın
5. Testi çalıştırın
6. Testler bittiğinde performans özeti görüntülenir (en hızlıdan yavaşa)

## Prompt Kategorileri

- **short**: 1-12 token (basit sorular)
- **medium**: 100-122 token (kod debug, algoritma)
- **long**: 1200-2300 token (proje analizi, mimari)
- **extra_long**: 17000-44000 token (büyük kod tabanları)

## Sonuçlar

Test sonuçları `results.txt` dosyasına kaydedilir:

```
Backend: LMSTUDIO
Model: deepseek-coder-v2-lite-16b
Prompt: medium_programming_debug_122t.txt

RESULTS:
  Run 1: 32.28 tok/s
  Run 2: 33.16 tok/s
  Run 3: 33.61 tok/s

AVERAGE: 33.02 tok/s
```

### Performans Özeti

Testler tamamlandığında, tüm sonuçlar hızdan yavaşa sıralı olarak gösterilir:

```
📊 PERFORMANCE SUMMARY (Fastest to Slowest)
================================================================================

1. model-name-1                          | prompt-file.txt                | 45.23 tok/s
2. model-name-2                          | prompt-file.txt                | 33.02 tok/s
3. model-name-3                          | prompt-file.txt                | 28.15 tok/s

================================================================================
```

## Yapılandırma

Ayarlar `~/.llm-benchmark-config.json` dosyasında saklanır:

```json
{
  "ollama_url": "http://localhost:11434",
  "llamacpp_url": "http://localhost:8080",
  "lmstudio_url": "http://localhost:1234",
  "test_iterations": 3
}
```

## Ek Testler

`machine_tests/` dizininde çeşitli performans testleri bulunmaktadır (opsiyonel).

## Lisans

MIT
