// Jobs.jsx
import { useState } from 'react'
import { MdManageSearch } from "react-icons/md";
import { Button, Checkbox, Drawer, Input, Radio, Select, Table, Upload } from "antd";
import { FaCirclePlay } from "react-icons/fa6";
import { IoIosAddCircle } from "react-icons/io";

import './App.css'
import { search, searchImage, searchOcr, searchAsr, asrSearch, ocrSearch } from './api';
import { Option } from 'antd/es/mentions';
import { InboxOutlined, MenuOutlined } from "@ant-design/icons";
import { CiLink } from "react-icons/ci";
import Infor from './Infor';
import { FaFolderOpen } from "react-icons/fa";
import YoutubePlayer from './YoutubePlayer.jsx';
import Ansbox from './Ansbox.jsx';
import Ansbox1 from './Ansbox1.jsx';
import Ansbox2 from './Ansbox2.jsx';
import TrakePanel from './TrakePanel.jsx';
import FrameCalc from './FrameCalc.jsx';
import AsrResults from './AsrResults.jsx';

const locationFromResult = (item) => {
  const source = typeof item === 'object' && item ? item : {};
  const candidate = [source.video_id, source.path, source.url]
    .filter(Boolean)
    .join(' ');
  const matched = candidate.match(/(?:[KL])?(\d+)_V(\d+)/i);
  const l = source.L ?? matched?.[1] ?? '';
  const v = source.V ?? matched?.[2] ?? '';

  return {
    L: String(l).replace(/^[KL]/i, ''),
    V: String(v).replace(/^V/i, ''),
  };
};

const compareCodes = (left, right) =>
  Number(left) - Number(right) || String(left).localeCompare(String(right));

function Jobs() {
  const [drawerOpen, setDrawerOpen] = useState(true); // mở mặc định
  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => setDrawerOpen(false);

  // UI state
  const [status, setStatus] = useState(false);
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [screen1, setScreen1] = useState("");
  const [screen2, setScreen2] = useState("");
  const [screen3, setScreen3] = useState("");
  const [lang, setLang] = useState("Eng")
  const [inf, setInf] = useState()

  const [selectedFrame, setSelectedFrame] = useState(null);
  const [selectAns, setSelectAns] = useState("KIS")
  const [mondalFLag, setModalFlag] = useState(false)
  const [vidFlag, setVidFlag] = useState('')
  const [ytflag, setYtflag] = useState(false)
  const [ansflag, setAnsflag] = useState(false)
  const [model, setModel] = useState("beit3")
  const [searchMode, setSearchMode] = useState("visual")
  const [fuzzyLevel, setFuzzyLevel] = useState(1)
  const [topk, setTopk] = useState(100)
  const [retrival, setRetrival] = useState([]) // array of objects {path, L, V, frame_id, ...}
  const [filterL, setFilterL] = useState(undefined)
  const [filterV, setFilterV] = useState(undefined)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState("")
  const [imageSearching, setImageSearching] = useState(false)

  // ASR search: 2 modes — standalone / merge into main search
  const [asrQuery, setAsrQuery] = useState("")
  const [asrMode, setAsrMode] = useState("standalone")
  const [asrResults, setAsrResults] = useState([])
  const [asrLoading, setAsrLoading] = useState(false)
  const [asrError, setAsrError] = useState("")

  const runAsrSearch = async () => {
    if (!asrQuery.trim()) { setAsrError("Enter spoken content to search"); return }
    setAsrError(""); setAsrLoading(true); setAsrResults([])
    try {
      const resp = await asrSearch({ query: asrQuery, k: 50 })
      if (resp.data?.ok) setAsrResults(resp.data.results || [])
      else setAsrError(resp.data?.error || "ASR search failed")
    } catch (err) {
      setAsrError(err?.response?.data?.error || err.message || "Backend connection error")
    } finally { setAsrLoading(false) }
  }
  const asrActive = asrMode === "standalone" && (asrLoading || asrError || asrResults.length > 0)

  // OCR search (chữ trên màn hình) — cùng pattern ASR; standalone tái dùng bảng frame (retrival)
  const [ocrQuery, setOcrQuery] = useState("")
  const [ocrMode, setOcrMode] = useState("standalone")
  const [ocrLoading, setOcrLoading] = useState(false)
  const [ocrError, setOcrError] = useState("")

  const runOcrSearch = async () => {
    if (!ocrQuery.trim()) { setOcrError("Enter on-screen text to search"); return }
    setOcrError(""); setOcrLoading(true)
    setFilterL(undefined); setFilterV(undefined); setPage(1)
    // xoá kết quả ASR standalone để bảng frame OCR hiện ra
    setAsrResults([]); setAsrError("")
    try {
      const resp = await ocrSearch({ query: ocrQuery, k: 100 })
      if (resp.data?.ok) setRetrival((resp.data.results || []).filter(Boolean))
      else { setOcrError(resp.data?.error || "OCR search failed"); setRetrival([]) }
    } catch (err) {
      setOcrError(err?.response?.data?.error || err.message || "Backend connection error"); setRetrival([])
    } finally { setOcrLoading(false) }
  }

  const availableLs = [...new Set(retrival.map(locationFromResult).map(({ L }) => L).filter(Boolean))]
    .sort(compareCodes);
  const availableVs = [...new Set(retrival
    .map(locationFromResult)
    .filter(({ L, V }) => V && (!filterL || L === filterL))
    .map(({ V }) => V))]
    .sort(compareCodes);
  const filteredRetrival = retrival.filter((item) => {
    const { L, V } = locationFromResult(item);
    return (!filterL || L === filterL) && (!filterV || V === filterV);
  });

  // normalize the filtered retrieval into rows of 5
  const rows = [];
  for (let i = 0; i < filteredRetrival.length; i += 5) {
    rows.push(filteredRetrival.slice(i, i + 5));
  }

  // columns dynamic: 5 columns
  const columns = Array.from({ length: 5 }, (_, idx) => ({
    title: `Item ${idx + 1}`,
    dataIndex: idx,
    key: idx,
    render: (item) => {
      if (!item) return null;

      // Normalize different possible shapes:
      // - string path: "keyframes/..."
      // - object: { path: "...", L: "21", V: "001", frame_id: 26, ... }
      // - sometimes backend might return absolute url in path
      const isString = typeof item === "string";
      let pathVal = isString ? item : (item.path || item.url || item.path_full || item.src || "");
      // If item is something like { idx: 123 } and metadata path missing, we can't render image
      // pathVal could also accidentally be an object; coerce to string
      if (pathVal && typeof pathVal !== "string") pathVal = String(pathVal);

      const imageUrl = pathVal
        ? (pathVal.startsWith("http://") || pathVal.startsWith("https://")
          ? pathVal
          : `/frames/${pathVal.replace(/^\/+/, '')}`)
        : null;

      // metadata fields
      const videoId = !isString && item ? (item.video_id || "") : "";
      const videoParts = videoId.split("_");
      const L = !isString && item
        ? (item.L || videoParts[0]?.replace(/^[KL]/, "") || "")
        : "";
      const V = !isString && item
        ? (item.V || videoParts[1]?.replace(/^V/, "") || "")
        : "";
      const frame_id = !isString && item
        ? (item.frame_id ?? item.frame_mid ?? (pathVal ? pathVal.split('/').pop() : ""))
        : (pathVal ? pathVal.split('/').pop() : "");
      const url = !isString && item ? item.video_url : "";
      const rawTime = !isString && item ? (item.frame_stamp ?? item.t_start ?? 0) : 0;
      const time = Number.isFinite(Number(rawTime)) ? Number(rawTime) : 0;
      const mstime = Math.floor(time * 1000)
      const fps = !isString && item ? (item.fps ?? "") : "";
      const metadataText = !isString && item ? (item.ocr_text || item.text || "") : "";
      let minute = Math.floor(time / 60)
      let sec = Math.floor(time - 60 * minute)
      const infor = {
        L: L,
        V: V,
        mstime: mstime,
        frame_id: frame_id,
        minute: minute,
        sec: sec,
        fps: fps
      }

      return (
        <div style={{ textAlign: "center" }}>
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={`frame-${frame_id}`}
              style={{ width: 300, height: 150, objectFit: "cover" }}
              onError={(e) => { e.currentTarget.src = ""; }}
            />
          ) : (
            <div style={{ width: 300, height: 150, display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f0f0" }}>
              No preview
            </div>
          )}
          <div>
            {`${L ? (parseInt(L.slice(0, 2)) <= 20 ? "K" : "L") + ": " + L : videoId}${V ? " - V: " + V : ""} ${frame_id !== "" ? "- " + frame_id : ""} - ${minute}m${sec.toFixed(0)}s ${fps}`}
            {url && <a href={`${url}&t=${time}s`} target="_blank" rel="noopener noreferrer"><CiLink /></a>}
          </div>
          {metadataText && (
            <div style={{ marginTop: 6, textAlign: "left", maxHeight: 72, overflow: "auto" }}>
              {metadataText}
            </div>
          )}
          <div className="result-action-buttons">
            {pathVal && <Button
              className="result-action-button"
              size="large"
              icon={<FaFolderOpen />}
              title="Xem các frame lân cận"
              aria-label="Xem các frame lân cận"
              onClick={() => {
                setModalFlag(true);
                setSelectedFrame({ idx: item.idx, L: item.L, V: item.V });
              }}
            />}
            {url && <Button
              className="result-action-button"
              size="large"
              icon={<FaCirclePlay />}
              title="Mở video tại thời điểm này"
              aria-label="Mở video tại thời điểm này"
              onClick={() => {
                setVidFlag(`${url}&t=${time}s`);
                setYtflag(true);
              }}
            />}
            <Button
              className="result-action-button"
              size="large"
              icon={<IoIosAddCircle />}
              title="Chọn kết quả để trả lời"
              aria-label="Chọn kết quả để trả lời"
              onClick={() => {
                setAnsflag(true)
                setInf(infor)
              }}
            />
          </div>





        </div>
      );
    }
  }));

  const dataSource = rows.map((row, index) => {
    const obj = { key: index };
    row.forEach((item, i) => {
      obj[i] = item;
    });
    return obj;
  });

  // Helper to call backend and normalize response
  const doSearch = async (payload, mode = "visual") => {
    try {
      console.log("Sending search payload:", payload);
      const requestSearch = mode === "ocr"
        ? searchOcr
        : mode === "asr"
          ? searchAsr
          : mode === "image"
            ? searchImage
            : search;
      const resp = await requestSearch(payload);

      // normalize possible response locations
      console.log(resp)
      const data = resp?.data ?? {};
      console.log("Raw server response:", data);

      // Prefer 'paths', fallback to 'data.paths', 'result', or top-level array
      let result = data.results ?? data.paths ?? data.result ?? data.data ?? data;

      // If result is object that contains paths
      if (result && typeof result === 'object' && !Array.isArray(result)) {
        // maybe structure { paths: [...], topk: [...] }
        if (Array.isArray(result.paths)) {
          result = result.paths;
        } else if (Array.isArray(data.paths)) {
          result = data.paths;
        } else if (Array.isArray(data.topk)) {
          // sometimes topk is indices; then we can't build paths
          result = [];
        } else {
          // not an array -> unknown; try to find any array inside
          const foundArray = Object.values(result).find(v => Array.isArray(v));
          result = foundArray ?? [];
        }
      }

      if (!Array.isArray(result)) {
        // try resp.data directly if it's array
        if (Array.isArray(resp?.data)) {
          result = resp.data;
        } else {
          result = [];
        }
      }

      // Normalize each entry to object with 'path' if necessary
      const normalized = result.map(r => {
        if (!r) return null;
        if (typeof r === "string") {
          return { path: r };
        } else if (typeof r === "object") {
          // If r contains only path-like string keys, keep as-is
          return r;
        } else {
          return null;
        }
      }).filter(Boolean);

      console.log("Normalized result count:", normalized.length, normalized.slice(0, 3));
      setFilterL(undefined);
      setFilterV(undefined);
      setPage(1);
      setRetrival(normalized);
      return normalized;
    } catch (err) {
      console.error("Search failed:", err?.response?.data ?? err.message ?? err);
      setRetrival([]);
      return [];
    }
  };

  // Handler for the search button(s)
  const handleSearchClick = async (withScreens = false) => {
    // ensure topk is a number
    const kNum = Number(topk) || 100;

    if (searchMode === "ocr" || searchMode === "asr") {
      const metadataQuery = (screen1 || "").trim();
      if (!metadataQuery) {
        setRetrival([]);
        return;
      }

      await doSearch({
        query: metadataQuery,
        limit: kNum,
        fuzzy_level: fuzzyLevel,
      }, searchMode);
      return;
    }

    const basePayload = {
      k: kNum,
      device: "cpu",
      page: 1,
      page_size: pageSize || 10,
      query1: screen1 || undefined,
      asr: asrMode === "merge" ? (asrQuery || undefined) : undefined,
      ocr: ocrMode === "merge" ? (ocrQuery || undefined) : undefined,
      language: lang

    };

    const payload = withScreens ? {
      ...basePayload,
      query1: screen1 || undefined,
      query2: screen2 || undefined,
      query3: screen3 || undefined,
      model: model || "beit3",
      augment: status,
      page: 1,
      page_size: pageSize || 10
    } : basePayload;

    await doSearch(payload);
  };

  const selectImage = (file) => {
    setImageFile(file);

    const reader = new FileReader();
    reader.onload = () => setImagePreview(String(reader.result || ""));
    reader.readAsDataURL(file);

    return false;
  };

  const clearImage = () => {
    setImageFile(null);
    setImagePreview("");
  };

  const handleImageSearch = async () => {
    if (!imageFile) return;

    const formData = new FormData();
    formData.append("image", imageFile);
    formData.append("model", model || "beit3");
    formData.append("top_k", String(Number(topk) || 100));

    setImageSearching(true);
    try {
      await doSearch(formData, "image");
      setSearchMode("visual");
      closeDrawer();
    } finally {
      setImageSearching(false);
    }
  };

  return (
    <>
      <div style={{ display: 'flex', width: '100%', position: 'relative', minHeight: '100vh' }}>
        {/* Sidebar Drawer */}
        <Drawer
          title={<h2 style={{ margin: 0, fontFamily: "sans-serif" }}>Image Search</h2>}
          placement="left"
          onClose={closeDrawer}
          open={drawerOpen}
          width={360}
          mask={false}
          closable={true}
          bodyStyle={{ padding: 20 }}
          style={{ height: "108vh", overflow: "hidden" }}
          getContainer={false}
        >
          <div style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            overflowY: "auto",
            background: "#fff",
          }}>
            <Upload.Dragger
              accept="image/jpeg,image/png,image/webp"
              beforeUpload={selectImage}
              fileList={imageFile ? [imageFile] : []}
              maxCount={1}
              multiple={false}
              onRemove={clearImage}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">Drag & drop image here</p>
              <p className="ant-upload-hint">Or click to select JPG, PNG, WEBP</p>
            </Upload.Dragger>

            {imagePreview && (
              <img
                src={imagePreview}
                alt="Image search preview"
                style={{ width: "100%", maxHeight: 260, objectFit: "contain", borderRadius: 8 }}
              />
            )}

            <div>
              Model: <strong>{model.toUpperCase()}</strong> · Top-K: <strong>{Number(topk) || 100}</strong>
            </div>

            <Button
              type="primary"
              size="large"
              disabled={!imageFile}
              loading={imageSearching}
              onClick={handleImageSearch}
            >
              Search by image
            </Button>

            {/* ASR search — spoken content, 2 modes */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontWeight: 600 }}>ASR search — spoken content</div>
              <Radio.Group value={asrMode} onChange={(e) => setAsrMode(e.target.value)}>
                <Radio value="standalone">Standalone</Radio>
                <Radio value="merge">Merge into main search</Radio>
              </Radio.Group>
              <Input.TextArea
                placeholder="e.g. the chairman announces the opening"
                value={asrQuery}
                autoSize={{ minRows: 2, maxRows: 4 }}
                onChange={(e) => setAsrQuery(e.target.value)}
              />
              {asrMode === "standalone" ? (
                <Button type="primary" loading={asrLoading} onClick={runAsrSearch}>
                  ASR Search
                </Button>
              ) : (
                <div style={{ fontSize: 12, color: "#888" }}>
                  ASR content merges into the main search (Screen 1/2/3) to push matching frames to the top.
                </div>
              )}
            </div>

            {/* OCR search — chữ trên màn hình, cùng 2 mode */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontWeight: 600 }}>OCR search — on-screen text</div>
              <Radio.Group value={ocrMode} onChange={(e) => setOcrMode(e.target.value)}>
                <Radio value="standalone">Standalone</Radio>
                <Radio value="merge">Merge into main search</Radio>
              </Radio.Group>
              <Input
                placeholder='e.g. proper noun, score "3 - 1"'
                value={ocrQuery}
                onChange={(e) => setOcrQuery(e.target.value)}
                onPressEnter={ocrMode === "standalone" ? runOcrSearch : undefined}
              />
              {ocrMode === "standalone" ? (
                <Button type="primary" loading={ocrLoading} onClick={runOcrSearch}>
                  OCR Search
                </Button>
              ) : (
                <div style={{ fontSize: 12, color: "#888" }}>
                  OCR text merges into the main search (Screen 1/2/3) to push matching frames to the top.
                </div>
              )}
              {ocrError && <div style={{ color: "#d4380d", fontSize: 12 }}>{ocrError}</div>}
            </div>

            <div style={{ borderTop: '1px solid #eee', margin: '6px 0' }} />
            <FrameCalc />
          </div>

        </Drawer>

        {/* Main area — dời sang phải khi mở sidebar để không bị che */}
        <div style={{
          width: drawerOpen ? 'calc(100% - 372px)' : '100%',
          marginLeft: drawerOpen ? '372px' : '0',
          transition: 'margin-left 0.2s ease, width 0.2s ease',
          fontFamily: 'Inter, sans-serif',
          padding: '12px',
          boxSizing: 'border-box',
        }}>

          {/* Search row */}
          <div
            style={{
              width: '100%',
              margin: 'auto',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '12px',
              background: '#fff',

              borderRadius: '10px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
            onKeyDown={async (e) => {
              if (e.key === 'Enter') {

                e.preventDefault();
                await handleSearchClick(screen1 !== '' || screen2 !== '');
              }}}
          >
            <Input
              style={{ flex: 1, borderRadius: 8 }}
              placeholder={searchMode === "visual" ? "Search a scene (1 query — use TRAKE for multiple events)" : "Enter OCR/ASR content"}
              value={screen1}
              onChange={(e) => setScreen1(e.target.value)}
            />

            <Button
              type="primary"
              shape="circle"
              onClick={async (e) => {
                e.preventDefault();
                await handleSearchClick(screen1 !== '' || screen2 !== '');
              }}
              title="Activate advanced searching"
            >
              <MdManageSearch size={18} />
            </Button>

            <Button
              type="text"
              onClick={openDrawer}
              icon={<MenuOutlined />}
              title="Advanced Searching"
            />
          </div>

          {/* Settings row */}
          <div
            style={{
              width: '100%',
              marginTop: '16px',
              display: 'flex',
              justifyContent: 'flex-end',
              alignItems: 'center',
              gap: '12px',
              background: '#fff',

              borderRadius: '10px',
              boxShadow: '0 1px 6px rgba(0,0,0,0.05)',
            }}
          >
            <Checkbox checked={lang} onChange={(e) => {
              if (e.target.checked) {
                setLang(true)
              } else {
                setLang(false)
              }
            }}>
              <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
                <img
                  src={`/tran.png`}
                  alt=""
                  style={{ width: "16px", height: "16px" }}
                />
                <p>Translate</p>
              </div>
            </Checkbox>

            <Checkbox checked={status} onChange={(e) => setStatus(e.target.checked)}>
              <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
                <p>Augment</p>
              </div>
            </Checkbox>
            <Input
              style={{ width: '120px', borderRadius: 8 }}
              placeholder="set top-K"
              value={topk}
              onChange={(e) => {
                const v = e.target.value;
                const n = Number(v);
                setTopk(Number.isNaN(n) ? v : n);
              }}
            />

            <Select
              style={{ width: '130px' }}
              value={model}
              onChange={(value) => setModel(value)}
            >
              <Option value="beit3">BEIT3</Option>
              <Option value="jina">JINA</Option>
              <Option value="pe">PE</Option>
            </Select>


            <Select
              style={{ width: '130px' }}
              value={selectAns}
              onChange={(value) => setSelectAns(value)}
            >
              <Option value="kis">KIS</Option>
              <Option value="qa">QA</Option>
              <Option value="trake">TRAKE</Option>

            </Select>




          </div>

          {/* Result area */}
          <div style={{ marginTop: 20 }}>
            {selectAns === "trake" ? (
              <TrakePanel language={lang === true} model={model} />
            ) : asrActive ? (
              <AsrResults loading={asrLoading} error={asrError} results={asrResults} />
            ) : retrival.length > 0 ? (
              <>
                <div className="result-filter-bar">
                  <span className="result-filter-count">
                    Hiển thị {filteredRetrival.length}/{retrival.length} kết quả
                  </span>
                  <Select
                    allowClear
                    className="result-filter-select"
                    placeholder="Lọc bộ L"
                    value={filterL}
                    onChange={(value) => {
                      setFilterL(value);
                      setFilterV(undefined);
                      setPage(1);
                    }}
                  >
                    {availableLs.map((value) => (
                      <Option key={value} value={value}>
                        {Number(value) <= 20 ? 'K' : 'L'}{value}
                      </Option>
                    ))}
                  </Select>
                  <Select
                    allowClear
                    className="result-filter-select"
                    placeholder="Lọc video V"
                    value={filterV}
                    onChange={(value) => { setFilterV(value); setPage(1); }}
                  >
                    {availableVs.map((value) => (
                      <Option key={value} value={value}>V{value}</Option>
                    ))}
                  </Select>
                </div>
                <Table
                  style={{ width: '100%', margin: '0', background: '#fff' }}
                  dataSource={dataSource}
                  columns={columns}
                  locale={{ emptyText: 'Không có kết quả phù hợp với bộ lọc L/V.' }}
                  pagination={{
                    current: page,
                    pageSize: pageSize,
                    showSizeChanger: true,
                    onChange: (page, pageSize) => {
                      setPage(page);
                      setPageSize(pageSize);
                    },
                  }}
                />
              </>
            ) : (
              <div
                style={{
                  fontFamily: 'Lexend, sans-serif',
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  height: '600px',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #f0f2f5, #fafafa)',
                  borderRadius: '12px',
                }}
              >
                <h1 style={{ fontSize: '65px', margin: 0 }}>EEIOT HCMUT</h1>
                <h2 style={{ fontSize: '40px', color: 'grey', margin: 0 }}>AIC 2025</h2>
              </div>
            )}
          </div>
        </div>

      </div>

      {mondalFLag && (
        <Infor
          setModalFlag={setModalFlag}

          selectedFrame={selectedFrame}
        />
      )}
      {ytflag && (
        <YoutubePlayer
          url={vidFlag}

          close={setYtflag}
        />
      )}
      {selectAns == "kis" && ansflag == true && (<Ansbox close={setAnsflag} inf={inf} />)}
      {selectAns == "qa" && ansflag == true && (<Ansbox1 close={setAnsflag} inf={inf} />)}

      {selectAns == "trake" && ansflag == true && (<Ansbox2 close={setAnsflag} inf={inf} />)}

    </>
  )
}

export default Jobs
