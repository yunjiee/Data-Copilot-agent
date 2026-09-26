// 以來執行測試生成簡報 node .\scripts\PPTX\test_generate_ppt.js

const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

async function runPptTest() {
    console.log("開始執行簡報產出測試...");
    let pres = new pptxgen();
    pres.layout = 'LAYOUT_16x9';
    pres.author = 'Presentation Agent';
    pres.title = '商品類別退貨率分析';

    // 色彩計畫設定 (Ocean Gradient)
    const COLOR_PRIMARY = "065A82";
    const COLOR_SECONDARY = "1C7293";
    const COLOR_ACCENT = "21295C";
    const COLOR_TEXT = "333333";
    const COLOR_BG_LIGHT = "F8F9FA";

    // 封面版面設計
    pres.defineSlideMaster({
      title: 'TITLE_SLIDE',
      background: { color: COLOR_PRIMARY },
      objects: [
        { rect: { x: 0, y: 4.8, w: '100%', h: 0.8, fill: { color: COLOR_ACCENT } } },
        { rect: { x: 0.5, y: 0.5, w: 0.1, h: 1.5, fill: { color: COLOR_SECONDARY } } }
      ]
    });

    // 內頁版面設計
    pres.defineSlideMaster({
      title: 'CONTENT_SLIDE',
      background: { color: COLOR_BG_LIGHT },
      objects: [
        { rect: { x: 0, y: 0, w: '100%', h: 0.8, fill: { color: COLOR_PRIMARY } } },
        { rect: { x: 0, y: 5.3, w: '100%', h: 0.3, fill: { color: COLOR_SECONDARY } } }
      ]
    });

    // [第1頁] 標題與封面
    let slide1 = pres.addSlide({ masterName: "TITLE_SLIDE" });
    slide1.addText("2022-07-01 至 2022-07-05", { x: 0.8, y: 1.5, w: 8, h: 0.5, fontSize: 18, color: "FFFFFF", fontFace: "Calibri Light" });
    slide1.addText("商品類別退貨率分析", { x: 0.8, y: 2.0, w: 8, h: 1.2, fontSize: 44, color: "FFFFFF", bold: true, fontFace: "Arial Black" });
    slide1.addText("整體表現報告", { x: 0.8, y: 3.2, w: 8, h: 0.6, fontSize: 24, color: "E0F2F1", fontFace: "Calibri" });

    // [第2頁] 查詢範圍與涵蓋類別
    let slide2 = pres.addSlide({ masterName: "CONTENT_SLIDE" });
    slide2.addText("查詢範圍與涵蓋類別", { x: 0.5, y: 0.1, w: 9, h: 0.6, fontSize: 28, color: "FFFFFF", bold: true, fontFace: "Arial Black" });
    slide2.addText([
      { text: "查詢期間：", options: { bold: true, color: COLOR_PRIMARY } },
      { text: "2022-07-01 至 2022-07-05\n", options: { color: COLOR_TEXT, breakLine: true } },
      { text: "分析對象：", options: { bold: true, color: COLOR_PRIMARY } },
      { text: "期間內 Top 20 熱銷商品", options: { color: COLOR_TEXT } }
    ], { x: 0.5, y: 1.2, w: 4, h: 1.2, fontSize: 18, fontFace: "Calibri" });

    slide2.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 2.5, w: 4.2, h: 2.3, fill: { color: "FFFFFF" },
      shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.1 }
    });

    slide2.addText("類別分佈重點", { x: 0.7, y: 2.7, w: 3.8, h: 0.4, fontSize: 18, bold: true, color: COLOR_PRIMARY });
    slide2.addText([
      { text: "Jeans (6件)", options: { bullet: true, breakLine: true } },
      { text: "Outerwear & Coats (4件)", options: { bullet: true, breakLine: true } },
      { text: "Pants (3件)", options: { bullet: true, breakLine: true } },
      { text: "Sweaters (2件)", options: { bullet: true, breakLine: true } },
      { text: "其他各 1件 (Sleep & Lounge等5類)", options: { bullet: true } }
    ], { x: 0.7, y: 3.2, w: 3.8, h: 1.4, fontSize: 16, color: COLOR_TEXT, fontFace: "Calibri" });

    // 引入由 test_chart.py 產出的 Vega-Lite 圖表圖片
    const chartPath = path.join(__dirname, '..', '..', 'output', 'test_sales_chart.png');
    if (fs.existsSync(chartPath)) {
      slide2.addImage({
        path: chartPath,
        x: 5.0,
        y: 1.3,
        w: 4.5,
        h: 3.5,
      });
      console.log(`📊 已將圖表加入第 2 頁: ${chartPath}`);
    }

    // [第3頁] 分析結果與結論
    let slide3 = pres.addSlide({ masterName: "CONTENT_SLIDE" });
    slide3.addText("分析結果與結論", { x: 0.5, y: 0.1, w: 9, h: 0.6, fontSize: 28, color: "FFFFFF", bold: true, fontFace: "Arial Black" });
    
    slide3.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: 1.5, w: 4, h: 3, fill: { color: "FFFFFF" },
      shadow: { type: "outer", color: "000000", blur: 8, offset: 3, angle: 135, opacity: 0.15 }
    });
    slide3.addText("0%", { x: 0.5, y: 2.0, w: 4, h: 1, fontSize: 72, bold: true, color: COLOR_PRIMARY, align: "center" });
    slide3.addText("退貨率與退貨件數", { x: 0.5, y: 3.0, w: 4, h: 0.5, fontSize: 20, color: COLOR_ACCENT, align: "center", bold: true });

    slide3.addText([
      { text: "分析結果", options: { bold: true, color: COLOR_PRIMARY, fontSize: 22, breakLine: true } },
      { text: "在上述期間與熱銷商品範圍內，所有商品類別的退貨件數皆為 0 件，退貨率皆為 0%。\n\n", options: { fontSize: 18, color: COLOR_TEXT, breakLine: true } },
      { text: "整體結論", options: { bold: true, color: COLOR_PRIMARY, fontSize: 22, breakLine: true } },
      { text: "整體表現非常良好，無退貨狀況，因此沒有所謂退貨率最高的商品類別。", options: { fontSize: 18, color: COLOR_TEXT } }
    ], { x: 5.0, y: 1.5, w: 4.5, h: 3, fontFace: "Calibri" });

    // 設定產出路徑為 output/本機端測試/
    const outputDir = path.join(__dirname, '..', '..', 'output', '本機端測試');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    const outputPath = path.join(outputDir, 'Rate_Analysis.pptx');
    
    try {
        await pres.writeFile({ fileName: outputPath });
        console.log(`✅ PPTX 簡報檔已成功生成！\n📂 檔案位置: ${outputPath}`);
    } catch (err) {
        if (err.code === "EBUSY") {
            console.error(`❌ 簡報生成失敗：檔案已被鎖定 (${outputPath})。\n👉 請先關閉正在開啟該簡報的 PowerPoint 或 Office 視窗後，再重新執行！`);
        } else {
            console.error("❌ 簡報生成失敗:", err);
        }
    }
}

runPptTest();