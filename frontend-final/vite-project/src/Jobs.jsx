// // Jobs.jsx
// import { useState } from 'react'
// import { MdManageSearch } from "react-icons/md";
// import { Button, Checkbox, Drawer, Input, InputNumber, Pagination, Popover, Radio, Select, Table, Tag, Upload } from "antd";
// import { FaCirclePlay } from "react-icons/fa6";
// import { IoIosAddCircle } from "react-icons/io";

// import './App.css'
// import { search, searchImage, searchOcr, searchAsr, searchCaption, asrSearch, ocrSearch, captionSearch, trafficSearch } from './api';
// import { Option } from 'antd/es/mentions';
// import { InboxOutlined, MenuOutlined, SlidersOutlined } from "@ant-design/icons";
// import { CiLink } from "react-icons/ci";
// import Infor from './Infor';
// import { FaFolderOpen } from "react-icons/fa";
// import YoutubePlayer from './YoutubePlayer.jsx';
// import Ansbox from './Ansbox.jsx';
// import Ansbox1 from './Ansbox1.jsx';
// import Ansbox2 from './Ansbox2.jsx';
// import TrakePanel from './TrakePanel.jsx';
// import FrameCalc from './FrameCalc.jsx';
// import AsrResults from './AsrResults.jsx';

// const locationFromResult = (item) => {
//   const source = typeof item === 'object' && item ? item : {};
//   const candidate = [source.video_id, source.path, source.url]
//     .filter(Boolean)
//     .join(' ');
//   const matched = candidate.match(/(?:[KL])?(\d+)_V(\d+)/i);
//   const l = source.L ?? matched?.[1] ?? '';
//   const v = source.V ?? matched?.[2] ?? '';

//   return {
//     L: String(l).replace(/^[KL]/i, ''),
//     V: String(v).replace(/^V/i, ''),
//   };
// };

// const compareCodes = (left, right) =>
//   Number(left) - Number(right) || String(left).localeCompare(String(right));

// function Jobs() {
//   const [drawerOpen, setDrawerOpen] = useState(false); // đóng mặc định — hero ở giữa, mở khi cần
//   const openDrawer = () => setDrawerOpen(true);
//   const closeDrawer = () => setDrawerOpen(false);

//   // UI state
//   const [status, setStatus] = useState(false);
//   const [page, setPage] = useState(1)
//   const [pageSize, setPageSize] = useState(24)
//   const [screen1, setScreen1] = useState("");
//   const [screen2, setScreen2] = useState("");
//   const [screen3, setScreen3] = useState("");
//   const [lang, setLang] = useState("Eng")
//   const [inf, setInf] = useState()

//   const [selectedFrame, setSelectedFrame] = useState(null);
//   const [selectAns, setSelectAns] = useState("KIS")
//   const [mondalFLag, setModalFlag] = useState(false)
//   const [vidFlag, setVidFlag] = useState('')
//   const [ytflag, setYtflag] = useState(false)
//   const [ansflag, setAnsflag] = useState(false)
//   const [model, setModel] = useState("beit3")
//   const [searchMode, setSearchMode] = useState("visual")
//   const [fuzzyLevel, setFuzzyLevel] = useState(1)
//   const [topk, setTopk] = useState(100)
//   const [retrival, setRetrival] = useState([]) // array of objects {path, L, V, frame_id, ...}
//   const [filterLs, setFilterLs] = useState([])
//   const [filterVs, setFilterVs] = useState([])
//   const [excludedScopes, setExcludedScopes] = useState([])
//   const [keepFilters, setKeepFilters] = useState(true)
//   const [imageFile, setImageFile] = useState(null)
//   const [imagePreview, setImagePreview] = useState("")
//   const [imageSearching, setImageSearching] = useState(false)

//   // ASR search: 2 modes — standalone / merge into main search
//   const [asrQuery, setAsrQuery] = useState("")
//   const [asrMode, setAsrMode] = useState("standalone")
//   const [asrResults, setAsrResults] = useState([])
//   const [asrLoading, setAsrLoading] = useState(false)
//   const [asrError, setAsrError] = useState("")

//   const runAsrSearch = async () => {
//     if (!asrQuery.trim()) { setAsrError("Enter spoken content to search"); return }
//     setAsrError(""); setAsrLoading(true); setAsrResults([])
//     try {
//       const resp = await asrSearch({ query: asrQuery, k: topk })
//       if (resp.data?.ok) setAsrResults(resp.data.results || [])
//       else setAsrError(resp.data?.error || "ASR search failed")
//     } catch (err) {
//       setAsrError(err?.response?.data?.error || err.message || "Backend connection error")
//     } finally { setAsrLoading(false) }
//   }
//   const asrActive = asrMode === "standalone" && (asrLoading || asrError || asrResults.length > 0)

//   // OCR search (chữ trên màn hình) — cùng pattern ASR; standalone tái dùng bảng frame (retrival)
//   const [ocrQuery, setOcrQuery] = useState("")
//   const [ocrMode, setOcrMode] = useState("standalone")
//   const [ocrLoading, setOcrLoading] = useState(false)
//   const [ocrError, setOcrError] = useState("")

//   const [captionQuery, setCaptionQuery] = useState("")
//   const [captionLoading, setCaptionLoading] = useState(false)
//   const [captionError, setCaptionError] = useState("")
  
//   const clearResultFilters = () => {
//     setFilterLs([])
//     setFilterVs([])
//     setExcludedScopes([])
//     setPage(1)
//   }

//   const prepareFiltersForNewSearch = () => {
//     if (!keepFilters) clearResultFilters()
//     else setPage(1)
//   }

//   const runOcrSearch = async () => {
//     if (!ocrQuery.trim()) { setOcrError("Enter on-screen text to search"); return }
//     setOcrError(""); setOcrLoading(true)
//     prepareFiltersForNewSearch()
//     // xoá kết quả ASR standalone để bảng frame OCR hiện ra
//     setAsrResults([]); setAsrError("")
//     try {
//       const resp = await ocrSearch({ query: ocrQuery, k: topk })
//       if (resp.data?.ok) setRetrival((resp.data.results || []).filter(Boolean))
//       else { setOcrError(resp.data?.error || "OCR search failed"); setRetrival([]) }
//     } catch (err) {
//       setOcrError(err?.response?.data?.error || err.message || "Backend connection error"); setRetrival([])
//     } finally { setOcrLoading(false) }
//   }

//   const runCaptionSearch = async () => {
//     if (!captionQuery.trim()) { setCaptionError("Enter keyframe caption to search"); return }
//     setCaptionError(""); setCaptionLoading(true)
//     setAsrResults([]); setAsrError("")
//     try {
//       const resp = await captionSearch({ query: captionQuery, k: topk })
//       if (resp.data?.ok) setRetrival((resp.data.results || []).filter(Boolean))
//       else { setCaptionError(resp.data?.error || "Caption search failed"); setRetrival([]) }
//     } catch (err) {
//       setCaptionError(err?.response?.data?.error || err.message || "Backend connection error"); setRetrival([])
//     } finally { setCaptionLoading(false) }
//   }

//   // normalize retrieval into rows of 5
//   const availableLs = [...new Set(retrival.map(locationFromResult).map(({ L }) => L).filter(Boolean))]
//     .sort(compareCodes);
//   const availableVs = [...new Set(retrival
//     .map(locationFromResult)
//     .filter(({ L, V }) => V && (!filterLs.length || filterLs.includes(L)))
//     .map(({ V }) => V))]
//     .sort(compareCodes);
//   const availableVideoPairs = [...new Map(
//     retrival.map(locationFromResult)
//       .filter(({ L, V }) => L && V)
//       .map(({ L, V }) => [`${L}:${V}`, { L, V }])
//   ).values()].sort((left, right) =>
//     compareCodes(left.L, right.L) || compareCodes(left.V, right.V)
//   );
//   const filteredRetrival = retrival.filter((item) => {
//     const { L, V } = locationFromResult(item);
//     // Lọc L và V theo từng tập độc lập. Khi chọn L01, L02 và V001:
//     // - L02 có V001 -> chỉ giữ L02_V001.
//     // - L01 không có V001 -> vẫn giữ toàn bộ L01, không bị thiếu kết quả.
//     const matchesIncludedL = !filterLs.length || filterLs.includes(L);
//     const selectedVideoExistsInThisL = filterVs.length > 0 && retrival.some((candidate) => {
//       const location = locationFromResult(candidate);
//       return location.L === L && filterVs.includes(location.V);
//     });
//     const matchesIncludedV = !filterVs.length
//       || !filterLs.length
//       || !selectedVideoExistsInThisL
//       || filterVs.includes(V);
//     const included = matchesIncludedL && matchesIncludedV;
//     const excluded = excludedScopes.includes(`l:${L}`)
//       || excludedScopes.includes(`lv:${L}:${V}`);
//     return included && !excluded;
//   });

//   // normalize the filtered retrieval into rows of 5
//   const rows = [];
//   for (let i = 0; i < filteredRetrival.length; i += 5) {
//     rows.push(filteredRetrival.slice(i, i + 5));
//   }

//   // columns dynamic: 5 columns
//   const columns = Array.from({ length: 5 }, (_, idx) => ({
//     title: `Item ${idx + 1}`,
//     dataIndex: idx,
//     key: idx,
//     render: (item) => {
//       if (!item) return null;

//       // Normalize different possible shapes:
//       // - string path: "keyframes/..."
//       // - object: { path: "...", L: "21", V: "001", frame_id: 26, ... }
//       // - sometimes backend might return absolute url in path
//       const isString = typeof item === "string";
//       let pathVal = isString ? item : (item.path || item.url || item.path_full || item.src || "");
//       // If item is something like { idx: 123 } and metadata path missing, we can't render image
//       // pathVal could also accidentally be an object; coerce to string
//       if (pathVal && typeof pathVal !== "string") pathVal = String(pathVal);

//       const imageUrl = pathVal
//         ? (pathVal.startsWith("http://") || pathVal.startsWith("https://")
//           ? pathVal
//           : `/frames/${pathVal.replace(/^\/+/, '')}`)
//         : null;

//       // metadata fields
//       const videoId = !isString && item ? (item.video_id || "") : "";
//       const videoParts = videoId.split("_");
//       const L = !isString && item
//         ? (item.L || videoParts[0]?.replace(/^[KL]/, "") || "")
//         : "";
//       const V = !isString && item
//         ? (item.V || videoParts[1]?.replace(/^V/, "") || "")
//         : "";
//       const frame_id = !isString && item
//         ? (item.frame_id ?? item.frame_mid ?? (pathVal ? pathVal.split('/').pop() : ""))
//         : (pathVal ? pathVal.split('/').pop() : "");
//       const url = !isString && item ? item.video_url : "";
//       const rawTime = !isString && item ? (item.frame_stamp ?? item.t_start ?? 0) : 0;
//       const time = Number.isFinite(Number(rawTime)) ? Number(rawTime) : 0;
//       const mstime = Math.floor(time * 1000)
//       const fps = !isString && item ? (item.fps ?? "") : "";
//       const metadataText = !isString && item ? (item.caption || item.ocr_text || item.text || "") : "";
//       let minute = Math.floor(time / 60)
//       let sec = Math.floor(time - 60 * minute)
//       const infor = {
//         L: L,
//         V: V,
//         mstime: mstime,
//         frame_id: frame_id,
//         minute: minute,
//         sec: sec,
//         fps: fps
//       }

//       return (
//         <div style={{ textAlign: "center" }}>
//           {imageUrl ? (
//             <img
//               src={imageUrl}
//               alt={`frame-${frame_id}`}
//               style={{ width: 300, height: 150, objectFit: "cover" }}
//               onError={(e) => { e.currentTarget.src = ""; }}
//             />
//           ) : (
//             <div style={{ width: 300, height: 150, display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f0f0" }}>
//               No preview
//             </div>
//           )}
//           <div>
//             {`${L ? (parseInt(L.slice(0, 2)) <= 20 ? "K" : "L") + ": " + L : videoId}${V ? " - V: " + V : ""} ${frame_id !== "" ? "- " + frame_id : ""} - ${minute}m${sec.toFixed(0)}s${fps !== "" && fps != null ? " · fps " + fps : ""}`}
//             {url && <a href={`${url}&t=${time}s`} target="_blank" rel="noopener noreferrer"><CiLink /></a>}
//           </div>
//           {metadataText && (
//             <div style={{ marginTop: 6, textAlign: "left", maxHeight: 72, overflow: "auto" }}>
//               {metadataText}
//             </div>
//           )}
//           {pathVal && <FaFolderOpen onClick={() => {
//             setModalFlag(true);
//             setSelectedFrame({
//               idx: item.idx,
//               L: item.L,
//               V: item.V,
//               video_id: item.video_id,
//             });
//           }} />}
//           {url && <FaCirclePlay onClick={() => {
//             let newUrl = `${url}&t=${time}s`; // Bỏ chữ 's'


//             setVidFlag(newUrl);
//             console.log("Setting vidFlag:", newUrl);
//             setYtflag(true);
//           }} />}
//           <IoIosAddCircle onClick={() => {
//             setAnsflag(true)
//             setInf(infor)
//           }} />
//           <div className="result-action-buttons">
//             {pathVal && <Button
//               className="result-action-button"
//               size="large"
//               icon={<FaFolderOpen />}
//               title="Xem các frame lân cận"
//               aria-label="Xem các frame lân cận"
//               onClick={() => {
//                 setModalFlag(true);
//                 setSelectedFrame({ idx: item.idx, L: item.L, V: item.V });
//               }}
//             />}
//             {url && <Button
//               className="result-action-button"
//               size="large"
//               icon={<FaCirclePlay />}
//               title="Mở video tại thời điểm này"
//               aria-label="Mở video tại thời điểm này"
//               onClick={() => {
//                 setVidFlag(`${url}&t=${time}s`);
//                 setYtflag(true);
//               }}
//             />}
//             <Button
//               className="result-action-button"
//               size="large"
//               icon={<IoIosAddCircle />}
//               title="Chọn kết quả để trả lời"
//               aria-label="Chọn kết quả để trả lời"
//               onClick={() => {
//                 setAnsflag(true)
//                 setInf(infor)
//               }}
//             />
//           </div>





//         </div>
//       );
//     }
//   }));

//   const dataSource = rows.map((row, index) => {
//     const obj = { key: index };
//     row.forEach((item, i) => {
//       obj[i] = item;
//     });
//     return obj;
//   });

//   // Helper to call backend and normalize response
//   const doSearch = async (payload, mode = "visual") => {
//     try {
//       console.log("Sending search payload:", payload);
//       const requestSearch = mode === "ocr"
//         ? searchOcr
//         : mode === "asr"
//           ? searchAsr
//           : mode === "caption"
//             ? searchCaption
//             : mode === "image"
//               ? searchImage
//               : search;
//       const resp = await requestSearch(payload);

//       // normalize possible response locations
//       console.log(resp)
//       const data = resp?.data ?? {};
//       console.log("Raw server response:", data);

//       // Prefer 'paths', fallback to 'data.paths', 'result', or top-level array
//       let result = data.results ?? data.paths ?? data.result ?? data.data ?? data;

//       // If result is object that contains paths
//       if (result && typeof result === 'object' && !Array.isArray(result)) {
//         // maybe structure { paths: [...], topk: [...] }
//         if (Array.isArray(result.paths)) {
//           result = result.paths;
//         } else if (Array.isArray(data.paths)) {
//           result = data.paths;
//         } else if (Array.isArray(data.topk)) {
//           // sometimes topk is indices; then we can't build paths
//           result = [];
//         } else {
//           // not an array -> unknown; try to find any array inside
//           const foundArray = Object.values(result).find(v => Array.isArray(v));
//           result = foundArray ?? [];
//         }
//       }

//       if (!Array.isArray(result)) {
//         // try resp.data directly if it's array
//         if (Array.isArray(resp?.data)) {
//           result = resp.data;
//         } else {
//           result = [];
//         }
//       }

//       // Normalize each entry to object with 'path' if necessary
//       const normalized = result.map(r => {
//         if (!r) return null;
//         if (typeof r === "string") {
//           return { path: r };
//         } else if (typeof r === "object") {
//           // If r contains only path-like string keys, keep as-is
//           return r;
//         } else {
//           return null;
//         }
//       }).filter(Boolean);

//       console.log("Normalized result count:", normalized.length, normalized.slice(0, 3));
//       // Bất kỳ search nào đổ vào bảng frame chính -> tắt panel ASR standalone để quay lại được semantic/OCR
//       setAsrResults([]);
//       setAsrError("");
//       prepareFiltersForNewSearch();
//       setRetrival(normalized);
//       return normalized;
//     } catch (err) {
//       console.error("Search failed:", err?.response?.data ?? err.message ?? err);
//       setAsrResults([]);
//       setAsrError("");
//       setRetrival([]);
//       return [];
//     }
//   };

//   // Handler for the search button(s)
//   const handleSearchClick = async (withScreens = false) => {
//     // ensure topk is a number
//     const kNum = Number(topk) || 100;

//     if (searchMode === "ocr" || searchMode === "asr" || searchMode === "caption") {
//       const metadataQuery = (screen1 || "").trim();
//       if (!metadataQuery) {
//         setRetrival([]);
//         return;
//       }

//       await doSearch({
//         query: metadataQuery,
//         k: kNum,
//         limit: kNum,
//         fuzzy_level: fuzzyLevel,
//       }, searchMode);
//       return;
//     }

//     const basePayload = {
//       k: kNum,
//       device: "cpu",
//       page: 1,
//       page_size: pageSize || 10,
//       query1: screen1 || undefined,
//       asr: asrMode === "merge" ? (asrQuery || undefined) : undefined,
//       ocr: ocrMode === "merge" ? (ocrQuery || undefined) : undefined,
//       language: lang

//     };

//     const payload = withScreens ? {
//       ...basePayload,
//       query1: screen1 || undefined,
//       query2: screen2 || undefined,
//       query3: screen3 || undefined,
//       model: model || "beit3",
//       augment: status,
//       page: 1,
//       page_size: pageSize || 10
//     } : basePayload;

//     await doSearch(payload);
//   };

//   const selectImage = (file) => {
//     setImageFile(file);

//     const reader = new FileReader();
//     reader.onload = () => setImagePreview(String(reader.result || ""));
//     reader.readAsDataURL(file);

//     return false;
//   };

//   const clearImage = () => {
//     setImageFile(null);
//     setImagePreview("");
//   };

//   const handleImageSearch = async () => {
//     if (!imageFile) return;

//     const formData = new FormData();
//     formData.append("image", imageFile);
//     formData.append("model", model || "beit3");
//     formData.append("top_k", String(Number(topk) || 100));

//     setImageSearching(true);
//     try {
//       await doSearch(formData, "image");
//       setSearchMode("visual");
//       closeDrawer();
//     } finally {
//       setImageSearching(false);
//     }
//   };

//   return (
//     <>
//       <div style={{ display: 'flex', width: '100%', position: 'relative', minHeight: '100vh' }}>
//         {/* Sidebar Drawer */}
//         <Drawer
//           title={<h2 style={{ margin: 0, fontFamily: "sans-serif" }}>Image Search</h2>}
//           placement="left"
//           onClose={closeDrawer}
//           open={drawerOpen}
//           width={360}
//           mask={false}
//           closable={true}
//           bodyStyle={{ padding: 20 }}
//           style={{ height: "108vh", overflow: "hidden" }}
//           getContainer={false}
//         >
//           <div style={{
//             height: "100%",
//             display: "flex",
//             flexDirection: "column",
//             gap: 16,
//             overflowY: "auto",
//             background: "#fff",
//           }}>
//             <Upload.Dragger
//               accept="image/jpeg,image/png,image/webp"
//               beforeUpload={selectImage}
//               fileList={imageFile ? [imageFile] : []}
//               maxCount={1}
//               multiple={false}
//               onRemove={clearImage}
//             >
//               <p className="ant-upload-drag-icon"><InboxOutlined /></p>
//               <p className="ant-upload-text">Drag & drop image here</p>
//               <p className="ant-upload-hint">Or click to select JPG, PNG, WEBP</p>
//             </Upload.Dragger>

//             {imagePreview && (
//               <img
//                 src={imagePreview}
//                 alt="Image search preview"
//                 style={{ width: "100%", maxHeight: 260, objectFit: "contain", borderRadius: 8 }}
//               />
//             )}

//             <div>
//               Model: <strong>{model.toUpperCase()}</strong> · Top-K: <strong>{Number(topk) || 100}</strong>
//             </div>

//             <Button
//               type="primary"
//               size="large"
//               disabled={!imageFile}
//               loading={imageSearching}
//               onClick={handleImageSearch}
//             >
//               Search by image
//             </Button>

//             {/* ASR search — spoken content, 2 modes */}
//             <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
//               <div style={{ fontWeight: 600 }}>ASR search — spoken content</div>
//               <Radio.Group value={asrMode} onChange={(e) => setAsrMode(e.target.value)}>
//                 <Radio value="standalone">Standalone</Radio>
//                 <Radio value="merge">Merge into main search</Radio>
//               </Radio.Group>
//               <Input.TextArea
//                 placeholder="e.g. the chairman announces the opening"
//                 value={asrQuery}
//                 autoSize={{ minRows: 2, maxRows: 4 }}
//                 onChange={(e) => setAsrQuery(e.target.value)}
//                 onPressEnter={(e) => {
//                   if (asrMode !== "standalone" || e.shiftKey) return;
//                   e.preventDefault();
//                   runAsrSearch();
//                 }}
//               />
//               {asrMode === "standalone" ? (
//                 <Button type="primary" loading={asrLoading} onClick={runAsrSearch}>
//                   ASR Search
//                 </Button>
//               ) : (
//                 <div style={{ fontSize: 12, color: "#888" }}>
//                   ASR content merges into the main search (Screen 1/2/3) to push matching frames to the top.
//                 </div>
//               )}
//             </div>

//             {/* OCR search — chữ trên màn hình, cùng 2 mode */}
//             <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
//               <div style={{ fontWeight: 600 }}>OCR search — on-screen text</div>
//               <Radio.Group value={ocrMode} onChange={(e) => setOcrMode(e.target.value)}>
//                 <Radio value="standalone">Standalone</Radio>
//                 <Radio value="merge">Merge into main search</Radio>
//               </Radio.Group>
//               <Input
//                 placeholder='e.g. proper noun, score "3 - 1"'
//                 value={ocrQuery}
//                 onChange={(e) => setOcrQuery(e.target.value)}
//                 onPressEnter={ocrMode === "standalone" ? runOcrSearch : undefined}
//               />
//               {ocrMode === "standalone" ? (
//                 <Button type="primary" loading={ocrLoading} onClick={runOcrSearch}>
//                   OCR Search
//                 </Button>
//               ) : (
//                 <div style={{ fontSize: 12, color: "#888" }}>
//                   OCR text merges into the main search (Screen 1/2/3) to push matching frames to the top.
//                 </div>
//               )}
//               {ocrError && <div style={{ color: "#d4380d", fontSize: 12 }}>{ocrError}</div>}
//             </div>

//             {/* Caption search - keyframe description */}
//             <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
//               <div style={{ fontWeight: 600 }}>Caption search - keyframe description</div>
//               <Input.TextArea
//                 placeholder="e.g. a man standing beside a red car"
//                 value={captionQuery}
//                 autoSize={{ minRows: 2, maxRows: 4 }}
//                 onChange={(e) => setCaptionQuery(e.target.value)}
//                 onPressEnter={runCaptionSearch}
//               />
//               <Button type="primary" loading={captionLoading} onClick={runCaptionSearch}>
//                 Caption Search
//               </Button>
//               {captionError && <div style={{ color: "#d4380d", fontSize: 12 }}>{captionError}</div>}
//             </div>

//             <div style={{ borderTop: '1px solid #eee', margin: '6px 0' }} />
//             <FrameCalc />
//           </div>

//         </Drawer>

//         {/* Main area — dời sang phải khi mở sidebar để không bị che */}
//         <div style={{
//           width: drawerOpen ? 'calc(100% - 372px)' : '100%',
//           marginLeft: drawerOpen ? '372px' : '0',
//           transition: 'margin-left 0.2s ease, width 0.2s ease',
//           fontFamily: 'Inter, sans-serif',
//           padding: '12px',
//           boxSizing: 'border-box',
//         }}>

//           {/* Search row */}
//           <div
//             style={{
//               width: '100%',
//               margin: 'auto',
//               display: 'flex',
//               justifyContent: 'space-between',
//               alignItems: 'center',
//               gap: '12px',
//               background: '#fff',

//               borderRadius: '10px',
//               boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
//             }}
//             onKeyDown={async (e) => {
//               if (e.key === 'Enter') {

//                 e.preventDefault();
//                 await handleSearchClick(screen1 !== '' || screen2 !== '');
//               }}}
//           >
//             <Input
//               style={{ flex: 1, borderRadius: 8 }}
//               placeholder={searchMode === "visual" ? "Search a scene (1 query — use TRAKE for multiple events)" : "Enter OCR/ASR content"}
//               value={screen1}
//               onChange={(e) => setScreen1(e.target.value)}
//             />

//             <Button
//               type="primary"
//               shape="circle"
//               onClick={async (e) => {
//                 e.preventDefault();
//                 await handleSearchClick(screen1 !== '' || screen2 !== '');
//               }}
//               title="Activate advanced searching"
//             >
//               <MdManageSearch size={18} />
//             </Button>

//             <Button
//               type="text"
//               onClick={openDrawer}
//               icon={<MenuOutlined />}
//               title="Advanced Searching"
//             />
//           </div>

//           {/* Settings row */}
//           <div
//             style={{
//               width: '100%',
//               marginTop: '16px',
//               display: 'flex',
//               justifyContent: 'flex-end',
//               alignItems: 'center',
//               gap: '12px',
//               background: '#fff',

//               borderRadius: '10px',
//               boxShadow: '0 1px 6px rgba(0,0,0,0.05)',
//             }}
//           >
//             <Checkbox checked={lang} onChange={(e) => {
//               if (e.target.checked) {
//                 setLang(true)
//               } else {
//                 setLang(false)
//               }
//             }}>
//               <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
//                 <img
//                   src={`/tran.png`}
//                   alt=""
//                   style={{ width: "16px", height: "16px" }}
//                 />
//                 <p>Translate</p>
//               </div>
//             </Checkbox>

//             <Checkbox checked={status} onChange={(e) => setStatus(e.target.checked)}>
//               <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
//                 <p>Augment</p>
//               </div>
//             </Checkbox>
//             <Input
//               style={{ width: '120px', borderRadius: 8 }}
//               placeholder="set top-K"
//               value={topk}
//               onChange={(e) => {
//                 const v = e.target.value;
//                 const n = Number(v);
//                 setTopk(Number.isNaN(n) ? v : n);
//               }}
//             />

//             <Select
//               style={{ width: '130px' }}
//               value={searchMode}
//               onChange={(value) => setSearchMode(value)}
//             >
//               <Option value="visual">VISUAL</Option>
//               <Option value="ocr">OCR</Option>
//               <Option value="asr">ASR</Option>
//               <Option value="caption">CAPTION</Option>
//             </Select>

//             <Select
//               style={{ width: '130px' }}
//               value={model}
//               onChange={(value) => setModel(value)}
//             >
//               <Option value="beit3">BEIT3</Option>
//               <Option value="jina">JINA</Option>
//               <Option value="pe">PE</Option>
//               <Option value="caption">CAPTION</Option>
//             </Select>


//             <Select
//               style={{ width: '130px' }}
//               value={selectAns}
//               onChange={(value) => setSelectAns(value)}
//             >
//               <Option value="kis">KIS</Option>
//               <Option value="qa">QA</Option>
//               <Option value="trake">TRAKE</Option>

//             </Select>




//           </div>

//           {/* Result area */}
//           <div style={{ marginTop: 20 }}>
//             {selectAns === "trake" ? (
//               <TrakePanel language={lang === true} model={model} />
//             ) : asrActive ? (
//               <AsrResults loading={asrLoading} error={asrError} results={asrResults} />
//             ) : retrival.length > 0 ? (
//               <>
//                 <div className="result-filter-bar">
//                   <span className="result-filter-count">
//                     Hiển thị {filteredRetrival.length}/{retrival.length} kết quả
//                   </span>
//                   <Select
//                     mode="multiple"
//                     allowClear
//                     className="result-filter-select"
//                     placeholder="Chọn một hoặc nhiều bộ L"
//                     value={filterLs}
//                     onChange={(values) => {
//                       setFilterLs(values);
//                       setFilterVs([]);
//                       setPage(1);
//                     }}
//                   >
//                     {availableLs.map((value) => (
//                       <Option key={value} value={value}>
//                         {Number(value) <= 20 ? 'K' : 'L'}{value}
//                       </Option>
//                     ))}
//                   </Select>
//                   <Select
//                     mode="multiple"
//                     allowClear
//                     className="result-filter-select"
//                     placeholder="V chỉ thu hẹp bộ L có video đó"
//                     value={filterVs}
//                     onChange={(values) => { setFilterVs(values); setPage(1); }}
//                   >
//                     {availableVs.map((value) => (
//                       <Option key={value} value={value}>V{value}</Option>
//                     ))}
//                   </Select>
             
//                   <Select
//                     mode="multiple"
//                     allowClear
//                     showSearch
//                     className="result-filter-select result-exclude-select"
//                     placeholder="Lọc bỏ L hoặc L_V"
//                     value={excludedScopes}
//                     onChange={(values) => { setExcludedScopes(values); setPage(1); }}
//                   >
//                     {availableLs.map((value) => (
//                       <Option key={`l:${value}`} value={`l:${value}`}>
//                         Bỏ toàn bộ {Number(value) <= 20 ? 'K' : 'L'}{value}
//                       </Option>
//                     ))}
//                     {availableVideoPairs.map(({ L, V }) => (
//                       <Option key={`lv:${L}:${V}`} value={`lv:${L}:${V}`}>
//                         Bỏ {Number(L) <= 20 ? 'K' : 'L'}{L}_V{V}
//                       </Option>
//                     ))}
//                   </Select>
//                   <Checkbox checked={keepFilters} onChange={(event) => setKeepFilters(event.target.checked)}>
//                     Giữ bộ lọc khi tìm kiếm mới
//                   </Checkbox>
//                   <Button size="small" onClick={clearResultFilters}>Xóa bộ lọc</Button>
//                 </div>
//                 <Table
//                   style={{ width: '100%', margin: '0', background: '#fff' }}
//                   dataSource={dataSource}
//                   columns={columns}
//                   locale={{ emptyText: 'Không có kết quả phù hợp với bộ lọc L/V.' }}
//                   pagination={{
//                     current: page,
//                     pageSize: pageSize,
//                     showSizeChanger: true,
//                     onChange: (page, pageSize) => {
//                       setPage(page);
//                       setPageSize(pageSize);
//                     },
//                   }}
//                 />
//               </>
//             ) : (
//               <div
//                 style={{
//                   fontFamily: 'Lexend, sans-serif',
//                   width: '100%',
//                   display: 'flex',
//                   flexDirection: 'column',
//                   alignItems: 'center',
//                   height: '600px',
//                   justifyContent: 'center',
//                   background: 'linear-gradient(135deg, #f0f2f5, #fafafa)',
//                   borderRadius: '12px',
//                 }}
//               >
//                 <h1 style={{ fontSize: '65px', margin: 0 }}>EEIOT HCMUT</h1>
//                 <h2 style={{ fontSize: '40px', color: 'grey', margin: 0 }}>AIC 2025</h2>
//               </div>
//             )}
//           </div>
//         </div>

//       </div>

//       {mondalFLag && (
//         <Infor
//           setModalFlag={setModalFlag}

//           selectedFrame={selectedFrame}
//         />
//       )}
//       {ytflag && (
//         <YoutubePlayer
//           url={vidFlag}

//           close={setYtflag}
//         />
//       )}
//       {selectAns == "kis" && ansflag == true && (<Ansbox close={setAnsflag} inf={inf} />)}
//       {selectAns == "qa" && ansflag == true && (<Ansbox1 close={setAnsflag} inf={inf} />)}

//       {selectAns == "trake" && ansflag == true && (<Ansbox2 close={setAnsflag} inf={inf} />)}

//     </>
//   )
// }

// export default Jobs

// Jobs.jsx
import { useState, useEffect } from 'react'
import { MdManageSearch } from "react-icons/md";
import { Button, Checkbox, Drawer, Input, InputNumber, Pagination, Popover, Radio, Select, Table, Tag, Upload } from "antd";
import { FaCirclePlay } from "react-icons/fa6";
import { IoIosAddCircle } from "react-icons/io";

import './App.css'
import { search, searchImage, searchOcr, searchAsr, searchCaption, asrSearch, ocrSearch, captionSearch, trafficSearch, ocrFilter, asrFilter, frameDetail } from './api';
import { Option } from 'antd/es/mentions';
import { InboxOutlined, MenuOutlined, SlidersOutlined } from "@ant-design/icons";
import { CiLink } from "react-icons/ci";
import Infor from './Infor';
import { FaFolderOpen } from "react-icons/fa";
import YoutubePlayer from './YoutubePlayer.jsx';
import TrakePanel from './TrakePanel.jsx';
import FrameCalc from './FrameCalc.jsx';
import AsrResults from './AsrResults.jsx';
import SubmissionModal from './SubmissionModal.jsx';

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
  const [drawerOpen, setDrawerOpen] = useState(false); // đóng mặc định — hero ở giữa, mở khi cần
  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => setDrawerOpen(false);

  // UI state
  const [status, setStatus] = useState(false);
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(24)
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
  const [detailItem, setDetailItem] = useState(null) // frame đang mở drawer chi tiết
  const [detailMeta, setDetailMeta] = useState(null) // metadata bổ sung (caption/OCR/ASR/objects) tra từ Mongo
  const [detailLoading, setDetailLoading] = useState(false)
  const [model, setModel] = useState("beit3")
  const [searchMode, setSearchMode] = useState("visual")
  const [fuzzyLevel, setFuzzyLevel] = useState(1)
  const [topk, setTopk] = useState(100)
  const [retrival, setRetrival] = useState([]) // array of objects {path, L, V, frame_id, ...}
  const [filterLs, setFilterLs] = useState([])
  const [filterVs, setFilterVs] = useState([])
  const [excludedScopes, setExcludedScopes] = useState([])
  const [keepFilters, setKeepFilters] = useState(true)
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
      const resp = await asrSearch({ query: asrQuery, k: topk })
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

  const [captionQuery, setCaptionQuery] = useState("")
  const [captionLoading, setCaptionLoading] = useState(false)
  const [captionError, setCaptionError] = useState("")

  // OCR/ASR chip popover: mode 'only' (standalone) | 'hybrid' (lọc trên kết quả semantic Top-K)
  const [ocrPopOpen, setOcrPopOpen] = useState(false)
  const [ocrChipMode, setOcrChipMode] = useState("only") // 'only' | 'hybrid'
  const [ocrHyQuery, setOcrHyQuery] = useState("")
  const [ocrHyOn, setOcrHyOn] = useState(false)          // hybrid filter đang bật
  const [asrPopOpen, setAsrPopOpen] = useState(false)
  const [asrChipMode, setAsrChipMode] = useState("only")
  const [asrHyQuery, setAsrHyQuery] = useState("")
  const [asrHyOn, setAsrHyOn] = useState(false)
  const [objPopOpen, setObjPopOpen] = useState(false) // popover chip Objects
  const [sortBy, setSortBy] = useState("relevance")    // relevance | time

  // Khi mở drawer chi tiết -> tra thêm caption/OCR/ASR/objects theo (video_id, frame_id).
  useEffect(() => {
    if (!detailItem) { setDetailMeta(null); return; }
    const vid = detailItem.video_id;
    const fid = detailItem.frame_id ?? detailItem.frame_mid;
    if (!vid || fid == null) { setDetailMeta(null); return; }
    let alive = true;
    setDetailLoading(true);
    setDetailMeta(null);
    frameDetail({ video_id: vid, frame_id: fid })
      .then((resp) => { if (alive && resp.data?.ok) setDetailMeta(resp.data.detail || null); })
      .catch(() => { if (alive) setDetailMeta(null); })
      .finally(() => { if (alive) setDetailLoading(false); });
    return () => { alive = false; };
  }, [detailItem]);

  // Traffic (detection/segmentation) — lọc frame video giao thông N theo thuộc tính detseg.
  const [trafMode, setTrafMode] = useState("standalone") // standalone | hybrid
  const [trafMinVehicle, setTrafMinVehicle] = useState()
  const [trafObjects, setTrafObjects] = useState([{ name: "", min: 1 }]) // danh sách object động {name, min}
  const [trafSort, setTrafSort] = useState("vehicle")
  const [trafLoading, setTrafLoading] = useState(false)
  const [trafError, setTrafError] = useState("")

  const setTrafObj = (i, field, val) =>
    setTrafObjects((prev) => prev.map((o, idx) => (idx === i ? { ...o, [field]: val } : o)))
  const addTrafObj = () => setTrafObjects((prev) => [...prev, { name: "", min: 1 }])
  const removeTrafObj = (i) => setTrafObjects((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)))
  // Quan hệ toạ độ giữa các object: {a, rel, b, c}
  const [trafRels, setTrafRels] = useState([])
  const setTrafRel = (i, field, val) =>
    setTrafRels((prev) => prev.map((r, idx) => (idx === i ? { ...r, [field]: val } : r)))
  const addTrafRel = () => setTrafRels((prev) => [...prev, { a: "", rel: "left", b: "", c: "" }])
  const removeTrafRel = (i) => setTrafRels((prev) => prev.filter((_, idx) => idx !== i))
  const TRAF_RELS = [
    { value: "left", label: "bên trái" }, { value: "right", label: "bên phải" },
    { value: "above", label: "phía trên" }, { value: "below", label: "phía dưới" },
    { value: "between", label: "ở giữa (A giữa B và C)" },
  ]
  // Class COCO (traffic trước, rồi phần còn lại) cho dropdown chọn object.
  const TRAFFIC_CLASSES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'person', 'train', 'boat',
    'traffic light', 'stop sign', 'fire hydrant', 'parking meter', 'bench', 'umbrella', 'backpack',
    'handbag', 'suitcase', 'dog', 'cat', 'bird', 'potted plant', 'chair', 'bottle', 'cup', 'cell phone',
    'clock', 'tv', 'laptop', 'skateboard', 'sports ball', 'kite', 'airplane']

  const clearResultFilters = () => {
    setFilterLs([])
    setFilterVs([])
    setExcludedScopes([])
    setPage(1)
  }

  const prepareFiltersForNewSearch = () => {
    if (!keepFilters) clearResultFilters()
    else setPage(1)
  }

  const runOcrSearch = async () => {
    if (!ocrQuery.trim()) { setOcrError("Enter on-screen text to search"); return }
    setOcrError(""); setOcrLoading(true)
    prepareFiltersForNewSearch()
    // xoá kết quả ASR standalone để bảng frame OCR hiện ra
    setAsrResults([]); setAsrError("")
    try {
      const resp = await ocrSearch({ query: ocrQuery, k: topk })
      if (resp.data?.ok) setRetrival((resp.data.results || []).filter(Boolean))
      else { setOcrError(resp.data?.error || "OCR search failed"); setRetrival([]) }
    } catch (err) {
      setOcrError(err?.response?.data?.error || err.message || "Backend connection error"); setRetrival([])
    } finally { setOcrLoading(false) }
  }

  const runCaptionSearch = async () => {
    if (!captionQuery.trim()) { setCaptionError("Enter keyframe caption to search"); return }
    setCaptionError(""); setCaptionLoading(true)
    setAsrResults([]); setAsrError("")
    try {
      const resp = await captionSearch({ query: captionQuery, k: topk })
      if (resp.data?.ok) setRetrival((resp.data.results || []).filter(Boolean))
      else { setCaptionError(resp.data?.error || "Caption search failed"); setRetrival([]) }
    } catch (err) {
      setCaptionError(err?.response?.data?.error || err.message || "Backend connection error"); setRetrival([])
    } finally { setCaptionLoading(false) }
  }

  // Traffic filter (video giao thông N).
  // - standalone: query detseg -> frame.
  // - hybrid: lọc kết quả semantic hiện tại (retrival) theo detseg, giữ thứ tự semantic.
  const runTrafficSearch = async () => {
    setTrafError(""); setTrafLoading(true)
    try {
      const payload = { k: Number(topk) || 100, sort: trafSort }
      if (trafMinVehicle) payload.min_vehicle = Number(trafMinVehicle)
      const objects = trafObjects
        .map((o) => ({ name: String(o.name || "").trim().toLowerCase(), min: Number(o.min) || 1 }))
        .filter((o) => o.name)
      if (objects.length) payload.objects = objects
      const relations = trafRels
        .map((r) => ({ a: r.a, rel: r.rel, b: r.b, c: r.c }))
        .filter((r) => r.a && r.b && (r.rel !== "between" || r.c))
      if (relations.length) payload.relations = relations

      if (trafMode === "hybrid") {
        // Gửi các frame semantic đang có để lọc; không có -> báo lỗi.
        const frames = retrival
          .map((r) => ({ video_id: r.video_id, frame_id: r.frame_id }))
          .filter((f) => f.video_id != null && f.frame_id != null)
        if (!frames.length) {
          setTrafError("Hybrid cần có kết quả semantic trước (search 1 câu rồi lọc).")
          setTrafLoading(false); return
        }
        payload.frames = frames
      } else {
        setAsrResults([]); setAsrError("")
      }

      const resp = await trafficSearch(payload)
      if (resp.data?.ok) { prepareFiltersForNewSearch(); setRetrival((resp.data.results || []).filter(Boolean)) }
      else { setTrafError(resp.data?.error || "Traffic search failed") }
    } catch (err) {
      setTrafError(err?.response?.data?.error || err.message || "Backend connection error")
    } finally { setTrafLoading(false) }
  }

  // normalize retrieval into rows of 5
  const availableLs = [...new Set(retrival.map(locationFromResult).map(({ L }) => L).filter(Boolean))]
    .sort(compareCodes);
  const availableVs = [...new Set(retrival
    .map(locationFromResult)
    .filter(({ L, V }) => V && (!filterLs.length || filterLs.includes(L)))
    .map(({ V }) => V))]
    .sort(compareCodes);
  const availableVideoPairs = [...new Map(
    retrival.map(locationFromResult)
      .filter(({ L, V }) => L && V)
      .map(({ L, V }) => [`${L}:${V}`, { L, V }])
  ).values()].sort((left, right) =>
    compareCodes(left.L, right.L) || compareCodes(left.V, right.V)
  );
  const filteredRetrival = retrival.filter((item) => {
    const { L, V } = locationFromResult(item);
    // Lọc L và V theo từng tập độc lập. Khi chọn L01, L02 và V001:
    // - L02 có V001 -> chỉ giữ L02_V001.
    // - L01 không có V001 -> vẫn giữ toàn bộ L01, không bị thiếu kết quả.
    const matchesIncludedL = !filterLs.length || filterLs.includes(L);
    const selectedVideoExistsInThisL = filterVs.length > 0 && retrival.some((candidate) => {
      const location = locationFromResult(candidate);
      return location.L === L && filterVs.includes(location.V);
    });
    const matchesIncludedV = !filterVs.length
      || !filterLs.length
      || !selectedVideoExistsInThisL
      || filterVs.includes(V);
    const included = matchesIncludedL && matchesIncludedV;
    const excluded = excludedScopes.includes(`l:${L}`)
      || excludedScopes.includes(`lv:${L}:${V}`);
    return included && !excluded;
  });

  // Sắp xếp: mặc định độ liên quan (thứ tự semantic gốc); hoặc theo thời gian trong video.
  const sortedRetrival = sortBy === 'time'
    ? [...filteredRetrival].sort((a, b) => (Number(a?.frame_stamp ?? a?.t_start ?? 0) || 0) - (Number(b?.frame_stamp ?? b?.t_start ?? 0) || 0))
    : filteredRetrival;

  // normalize the filtered retrieval into rows of 5
  const rows = [];
  for (let i = 0; i < filteredRetrival.length; i += 5) {
    rows.push(filteredRetrival.slice(i, i + 5));
  }
  const pagedRetrival = sortedRetrival.slice((page - 1) * pageSize, page * pageSize);

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
      const metadataText = !isString && item ? (item.caption || item.ocr_text || item.text || "") : "";
      let minute = Math.floor(time / 60)
      let sec = Math.floor(time - 60 * minute)
      const infor = {
        video_id: videoId,
        L: L,
        V: V,
        mstime: mstime,
        frame_id: frame_id,
        minute: minute,
        sec: sec,
        fps: fps
      }

      // Nhãn video: batch2 (N/S/M hoặc video_id có '-') dùng thẳng video_id; batch1 mới ép K/L theo số.
      const isBatch2 = /^[NSM]/i.test(String(videoId)) || /^[NSM]/i.test(String(L)) || String(videoId).includes('-')
      const videoLabel = isBatch2
        ? (videoId || `${L}${V ? " - V: " + V : ""}`)
        : `${L ? (parseInt(L.slice(0, 2)) <= 20 ? "K" : "L") + ": " + L : videoId}${V ? " - V: " + V : ""}`

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
            {`${videoLabel} ${frame_id !== "" ? "- " + frame_id : ""} - ${minute}m${sec.toFixed(0)}s${fps !== "" && fps != null ? " · fps " + fps : ""}`}
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
                setSelectedFrame({
                  idx: item.idx,
                  frame_id: frame_id,   // khoá bền hơn idx (idx Qdrant ≠ idx Mongo cho N/M/S)
                  L: Number(String(L).replace(/^[KL]/i, '')),
                  V: Number(String(V).replace(/^V/i, '')),
                  video_id: videoId,
                });
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

  // Hybrid: lọc 1 tập frame theo OCR/ASR query (giữ nguyên thứ tự semantic).
  const hybridFilterFrames = async (kind, arr, qy) => {
    const frames = arr
      .map((x) => ({ video_id: x.video_id, frame_id: x.frame_id }))
      .filter((f) => f.video_id && f.frame_id != null);
    if (!frames.length || !qy) return arr;
    try {
      const call = kind === "ocr" ? ocrFilter : asrFilter;
      const resp = await call({ frames, query: qy });
      const keep = new Set((resp.data?.results || []).map((r) => `${r.video_id}|${r.frame_id}`));
      return arr.filter((x) => keep.has(`${x.video_id}|${x.frame_id}`));
    } catch {
      return arr;
    }
  };

  // Áp cả 2 filter hybrid (OCR rồi ASR) — AND semantics.
  const applyHybridFilters = async (base) => {
    let arr = base;
    if (ocrHyOn && ocrHyQuery.trim()) arr = await hybridFilterFrames("ocr", arr, ocrHyQuery.trim());
    if (asrHyOn && asrHyQuery.trim()) arr = await hybridFilterFrames("asr", arr, asrHyQuery.trim());
    return arr;
  };

  // Apply từ popover chip OCR / ASR.
  const runChip = async (kind) => {
    const isOcr = kind === "ocr";
    const qy = (isOcr ? ocrHyQuery : asrHyQuery).trim();
    const mode = isOcr ? ocrChipMode : asrChipMode;
    if (isOcr) setOcrPopOpen(false); else setAsrPopOpen(false);

    if (mode === "only") {
      // Standalone: OCR -> bảng frame; ASR -> dải keyframe
      if (isOcr) { setOcrHyOn(false); setSearchMode("ocr"); }
      else { setAsrHyOn(false); setSearchMode("asr"); }
      if (!qy) return;
      if (isOcr) {
        setAsrResults([]); setAsrError(""); setOcrLoading(true);
        try {
          prepareFiltersForNewSearch();
          const resp = await ocrSearch({ query: qy, k: Number(topk) || 100 });
          setRetrival(resp.data?.ok ? (resp.data.results || []).filter(Boolean) : []);
        } catch { setRetrival([]); } finally { setOcrLoading(false); }
      } else {
        setAsrMode("standalone"); setAsrError(""); setAsrLoading(true); setAsrResults([]);
        try {
          const resp = await asrSearch({ query: qy, k: Number(topk) || 100 });
          if (resp.data?.ok) setAsrResults(resp.data.results || []);
          else setAsrError(resp.data?.error || "ASR search failed");
        } catch (err) {
          setAsrError(err?.response?.data?.error || err.message || "Backend connection error");
        } finally { setAsrLoading(false); }
      }
      return;
    }

    // Hybrid: bật filter, quay về semantic; lọc ngay trên kết quả hiện có (nếu có).
    if (isOcr) setOcrHyOn(!!qy); else setAsrHyOn(!!qy);
    if (searchMode === "ocr" || searchMode === "asr") { setSearchMode("visual"); setAsrResults([]); }
    if (qy && retrival.length) {
      const filtered = await hybridFilterFrames(kind, retrival, qy);
      setRetrival(filtered);
    }
  };

  const chipLabel = (base, mode, on) => (on ? `${base} · Hybrid` : (searchMode === base.toLowerCase() ? `${base} · Only` : base));

  // Objects (traffic detseg) filter panel — dùng trong Popover của chip "Objects".
  const trafficPanel = (
    <div style={{ width: 380, maxHeight: '64vh', overflowY: 'auto', display: "flex", flexDirection: "column", gap: 8, paddingRight: 4 }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.06em', color: '#94A3B8', textTransform: 'uppercase' }}>Objects — video giao thông (N)</div>
      <Radio.Group value={trafMode} onChange={(e) => setTrafMode(e.target.value)} size="small">
        <Radio value="standalone">Standalone</Radio>
        <Radio value="hybrid">Hybrid (lọc semantic)</Radio>
      </Radio.Group>
      <InputNumber size="small" min={1} placeholder="≥ tổng xe (vehicle)" value={trafMinVehicle}
        onChange={setTrafMinVehicle} style={{ width: 170 }} />
      {trafObjects.map((o, i) => (
        <div key={i} style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <Select size="small" showSearch allowClear placeholder="object" value={o.name || undefined}
            onChange={(v) => setTrafObj(i, "name", v || "")}
            options={TRAFFIC_CLASSES.map((c) => ({ value: c, label: c }))}
            style={{ flex: 1, minWidth: 130 }} />
          <InputNumber size="small" min={1} value={o.min}
            onChange={(v) => setTrafObj(i, "min", v || 1)} style={{ width: 64 }} />
          <Button size="small" type="text" danger disabled={trafObjects.length <= 1}
            onClick={() => removeTrafObj(i)}>✕</Button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Button size="small" icon={<IoIosAddCircle />} onClick={addTrafObj}>Thêm object</Button>
        {trafMode === "standalone" && (
          <Select size="small" value={trafSort} onChange={setTrafSort} style={{ width: 150 }}>
            <Option value="vehicle">Sort: nhiều xe</Option>
            <Option value="congestion">Sort: đông đúc</Option>
          </Select>
        )}
      </div>
      <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>Quan hệ vị trí (tuỳ chọn):</div>
      {trafRels.map((r, i) => (
        <div key={i} style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
          <Select size="small" showSearch placeholder="A" value={r.a || undefined}
            onChange={(v) => setTrafRel(i, "a", v || "")}
            options={TRAFFIC_CLASSES.map((c) => ({ value: c, label: c }))} style={{ width: 96 }} />
          <Select size="small" value={r.rel} onChange={(v) => setTrafRel(i, "rel", v)}
            options={TRAF_RELS} style={{ width: 96 }} />
          <Select size="small" showSearch placeholder="B" value={r.b || undefined}
            onChange={(v) => setTrafRel(i, "b", v || "")}
            options={TRAFFIC_CLASSES.map((c) => ({ value: c, label: c }))} style={{ width: 96 }} />
          {r.rel === "between" && (
            <Select size="small" showSearch placeholder="C" value={r.c || undefined}
              onChange={(v) => setTrafRel(i, "c", v || "")}
              options={TRAFFIC_CLASSES.map((c) => ({ value: c, label: c }))} style={{ width: 96 }} />
          )}
          <Button size="small" type="text" danger onClick={() => removeTrafRel(i)}>✕</Button>
        </div>
      ))}
      <Button size="small" icon={<IoIosAddCircle />} onClick={addTrafRel} style={{ alignSelf: "flex-start" }}>Thêm quan hệ</Button>
      <Button type="primary" loading={trafLoading} onClick={() => { setObjPopOpen(false); runTrafficSearch(); }}>
        {trafMode === "hybrid" ? "Lọc kết quả hiện tại" : "Objects Search"}
      </Button>
      {trafMode === "hybrid" && (
        <div style={{ fontSize: 12, color: "#888" }}>
          Hybrid: search 1 câu semantic trước, rồi lọc frame giao thông theo thuộc tính (giữ thứ tự semantic).
        </div>
      )}
      {trafError && <div style={{ color: "#d4380d", fontSize: 12 }}>{trafError}</div>}
    </div>
  );

  // Card grid renderer (thay Table) — dung cho semantic / OCR / caption / traffic.
  const renderResultCard = (item, key) => {
    if (!item) return null;
    const isString = typeof item === "string";
    let pathVal = isString ? item : (item.path || item.url || item.path_full || item.src || "");
    if (pathVal && typeof pathVal !== "string") pathVal = String(pathVal);
    const imageUrl = pathVal
      ? (pathVal.startsWith("http") ? pathVal : `/frames/${pathVal.replace(/^\/+/, '')}`)
      : null;
    const videoId = !isString && item ? (item.video_id || "") : "";
    const videoParts = videoId.split("_");
    const L = !isString && item ? (item.L || videoParts[0]?.replace(/^[KL]/, "") || "") : "";
    const V = !isString && item ? (item.V || videoParts[1]?.replace(/^V/, "") || "") : "";
    const frame_id = !isString && item
      ? (item.frame_id ?? item.frame_mid ?? (pathVal ? pathVal.split('/').pop() : ""))
      : (pathVal ? pathVal.split('/').pop() : "");
    const url = !isString && item ? item.video_url : "";
    const rawTime = !isString && item ? (item.frame_stamp ?? item.t_start ?? 0) : 0;
    const time = Number.isFinite(Number(rawTime)) ? Number(rawTime) : 0;
    const mstime = Math.floor(time * 1000);
    const fps = !isString && item ? (item.fps ?? "") : "";
    const metadataText = !isString && item ? (item.caption || item.ocr_text || item.text || "") : "";
    const score = !isString && item && typeof item.score === "number" ? item.score : null;
    const minute = Math.floor(time / 60);
    const sec = Math.floor(time - 60 * minute);
    const infor = { video_id: videoId, L, V, mstime, frame_id, minute, sec, fps };
    // Tag modality gọn để scan nhanh (dựa trên dữ liệu thực có của item)
    const cardTags = [];
    if (score != null) cardTags.push('Visual');
    if (!isString && item?.caption) cardTags.push('Caption');
    if (!isString && item?.ocr_text) cardTags.push(ocrHyOn ? 'OCR·Hy' : 'OCR');
    if (!isString && item?.counts) cardTags.push('Objects');
    const isBatch2 = /^[NSM]/i.test(String(videoId)) || /^[NSM]/i.test(String(L)) || String(videoId).includes('-');
    const videoLabel = isBatch2
      ? (videoId || `${L}${V ? " V" + V : ""}`)
      : `${L ? (parseInt(L.slice(0, 2)) <= 20 ? "K" : "L") + L : videoId}${V ? " V" + V : ""}`;

    return (
      <div key={key} className="result-card" onClick={() => setDetailItem(item)}>
        <div className="result-thumb">
          {imageUrl
            ? <img src={imageUrl} alt={`frame-${frame_id}`} loading="lazy" onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
            : <div className="result-noimg">No preview</div>}
          {score != null && <span className="result-score">{score.toFixed(2)}</span>}
          <span className="result-time-badge">{minute}m{sec.toFixed(0)}s</span>
          <div className="result-hover-actions">
            {pathVal && <button className="ra-btn" title="Xem frame lan can (+/-10)" onClick={(e) => {
              e.stopPropagation();
              setModalFlag(true);
              setSelectedFrame({ idx: item.idx, frame_id, L: Number(String(L).replace(/^[KL]/i, '')), V: Number(String(V).replace(/^V/i, '')), video_id: videoId });
            }}><FaFolderOpen /></button>}
            {url && <button className="ra-btn" title="Mo video" onClick={(e) => { e.stopPropagation(); setVidFlag(`${url}&t=${time}s`); setYtflag(true); }}><FaCirclePlay /></button>}
            <button className="ra-btn ra-btn-primary" title="Nop ket qua nay" onClick={(e) => { e.stopPropagation(); setAnsflag(true); setInf(infor); }}><IoIosAddCircle /></button>
          </div>
        </div>
        <div className="result-meta">
          <div className="result-vid">
            {`${videoLabel}${frame_id !== "" ? " · " + frame_id : ""} · ${minute}m${sec.toFixed(0)}s${fps !== "" && fps != null ? " · fps " + fps : ""}`}
            {url && <a href={`${url}&t=${time}s`} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 4 }}><CiLink /></a>}
          </div>
          {metadataText && <div className="result-caption">{metadataText}</div>}
          {cardTags.length > 0 && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 8 }}>
              {cardTags.map((t) => {
                const hy = t.includes('Hy');
                return (
                  <span key={t} style={{
                    fontSize: 11, fontWeight: 600, padding: '1px 8px', borderRadius: 999,
                    border: `1px solid ${hy ? '#1677FF' : '#E2E8F0'}`,
                    color: hy ? '#1677FF' : '#64748B', background: hy ? '#EFF6FF' : '#F8FAFC',
                  }}>{t}</span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  };

  // Helper to call backend and normalize response
  const doSearch = async (payload, mode = "visual") => {
    try {
      console.log("Sending search payload:", payload);
      const requestSearch = mode === "ocr"
        ? searchOcr
        : mode === "asr"
          ? searchAsr
          : mode === "caption"
            ? searchCaption
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
      // Bất kỳ search nào đổ vào bảng frame chính -> tắt panel ASR standalone để quay lại được semantic/OCR
      setAsrResults([]);
      setAsrError("");
      prepareFiltersForNewSearch();
      setRetrival(normalized);
      return normalized;
    } catch (err) {
      console.error("Search failed:", err?.response?.data ?? err.message ?? err);
      setAsrResults([]);
      setAsrError("");
      setRetrival([]);
      return [];
    }
  };

  // Handler for the search button(s)
  // Search hợp nhất: route theo modality (searchMode) từ thanh search chính + query screen1.
  const handleSearchClick = async () => {
    const kNum = Number(topk) || 100;
    const q = (screen1 || "").trim();

    if (searchMode === "trake") return;              // TrakePanel tự xử lý (nhập event riêng)
    if (searchMode === "traffic") { await runTrafficSearch(); return; }

    if (searchMode === "asr") {                        // ASR -> AsrResults (dải keyframe)
      if (!q) { setAsrError("Nhập nội dung lời nói cần tìm"); return; }
      setAsrMode("standalone"); setAsrError(""); setAsrLoading(true); setAsrResults([]);
      try {
        const resp = await asrSearch({ query: q, k: kNum });
        if (resp.data?.ok) setAsrResults(resp.data.results || []);
        else setAsrError(resp.data?.error || "ASR search failed");
      } catch (err) {
        setAsrError(err?.response?.data?.error || err.message || "Backend connection error");
      } finally { setAsrLoading(false); }
      return;
    }

    if (searchMode === "ocr" || searchMode === "caption") {  // -> bảng frame (retrival)
      if (!q) { setRetrival([]); return; }
      setAsrResults([]); setAsrError(""); setOcrLoading(true);
      try {
        prepareFiltersForNewSearch();
        const api = searchMode === "ocr" ? ocrSearch : captionSearch;
        const resp = await api({ query: q, k: kNum });
        let base = resp.data?.ok ? (resp.data.results || []).filter(Boolean) : [];
        setRetrival(base);
        // caption cho phép hybrid lọc thêm OCR/ASR
        if (searchMode === "caption" && ((ocrHyOn && ocrHyQuery.trim()) || (asrHyOn && asrHyQuery.trim()))) {
          const filtered = await applyHybridFilters(base);
          if (filtered.length !== base.length) setRetrival(filtered);
        }
      } catch (err) { setRetrival([]); }
      finally { setOcrLoading(false); }
      return;
    }

    // visual (semantic) -> có thể lọc lại bằng hybrid OCR/ASR
    const base = await doSearch({
      k: kNum, device: "cpu", page: 1, page_size: pageSize || 10,
      query1: screen1 || undefined, model: model || "beit3", augment: status, language: lang,
    });
    if ((ocrHyOn && ocrHyQuery.trim()) || (asrHyOn && asrHyQuery.trim())) {
      const filtered = await applyHybridFilters(base);
      if (filtered.length !== base.length) setRetrival(filtered);
    }
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
      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50, height: 64, background: '#fff',
        borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', padding: '0 24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, color: '#fff', fontWeight: 700,
            background: 'linear-gradient(135deg,#1677FF,#0F2747)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>▲</div>
          <span style={{ fontWeight: 700, fontSize: 18, color: '#0F2747' }}>AIC 2026</span>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <span style={{ color: '#64748B', fontWeight: 500 }}>Multimodal Search</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#16A34A' }} />
            <div style={{ lineHeight: 1.25, textAlign: 'right' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#172033' }}>Dataset ready</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Team <b style={{ color: '#1677FF' }}>MLIoT_Newbie</b></div>
            </div>
          </div>
          <Button type="text" shape="circle" icon={<MenuOutlined />} onClick={openDrawer} title="Tùy chọn nâng cao" />
        </div>
      </header>

      <div style={{ display: 'flex', width: '100%', position: 'relative', minHeight: 'calc(100vh - 64px)' }}>
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
                onPressEnter={(e) => {
                  if (asrMode !== "standalone" || e.shiftKey) return;
                  e.preventDefault();
                  runAsrSearch();
                }}
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

            {/* Caption search - keyframe description */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontWeight: 600 }}>Caption search - keyframe description</div>
              <Input.TextArea
                placeholder="e.g. a man standing beside a red car"
                value={captionQuery}
                autoSize={{ minRows: 2, maxRows: 4 }}
                onChange={(e) => setCaptionQuery(e.target.value)}
                onPressEnter={runCaptionSearch}
              />
              <Button type="primary" loading={captionLoading} onClick={runCaptionSearch}>
                Caption Search
              </Button>
              {captionError && <div style={{ color: "#d4380d", fontSize: 12 }}>{captionError}</div>}
            </div>

            {/* Objects (traffic) filter đã chuyển sang Popover của chip "Objects" ở thanh chip. */}

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

          {/* Hero search */}
          <div style={{ maxWidth: 920, margin: '4px auto 0' }}>
            {retrival.length === 0 && !asrActive && selectAns !== 'trake' && (
              <div style={{ textAlign: 'center', margin: '28px 0 18px' }}>
                <h1 style={{ fontSize: 30, fontWeight: 700, color: '#0F2747', margin: 0 }}>Multimodal Video Search</h1>
                <p style={{ color: '#64748B', marginTop: 6, fontSize: 15 }}>
                  Tìm kiếm video bằng văn bản, hình ảnh, giọng nói và chữ trên màn hình.
                </p>
              </div>
            )}
            <div
              style={{
                display: 'flex', gap: 10, alignItems: 'center', background: '#fff',
                border: '1px solid #E2E8F0', borderRadius: 14, padding: '6px 6px 6px 16px',
                boxShadow: '0 1px 3px rgba(16,24,40,.08)',
              }}
              onKeyDown={async (e) => {
                if (e.key === 'Enter') { e.preventDefault(); await handleSearchClick(screen1 !== '' || screen2 !== ''); }
              }}
            >
              <MdManageSearch size={22} color="#94A3B8" />
              <Input
                variant="borderless"
                style={{ flex: 1, fontSize: 15 }}
                placeholder={searchMode === "visual" ? "Mô tả cảnh cần tìm (1 câu — dùng TRAKE cho nhiều sự kiện)" : "Nhập nội dung OCR / ASR / Caption"}
                value={screen1}
                onChange={(e) => setScreen1(e.target.value)}
              />
              <Popover
                trigger="click"
                placement="bottomRight"
                content={
                  <div style={{ width: 268, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.04em', color: '#667085' }}>RETRIEVAL</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Select value={model} onChange={(v) => setModel(v)} style={{ flex: 1 }}
                        options={[{ value: 'beit3', label: 'BEIT3' }, { value: 'jina', label: 'JINA' }, { value: 'pe', label: 'PE' }, { value: 'caption', label: 'CAPTION' }]} />
                      <Input style={{ width: 92 }} placeholder="top-K" value={topk}
                        onChange={(e) => { const n = Number(e.target.value); setTopk(Number.isNaN(n) ? e.target.value : n); }} />
                    </div>
                    <div style={{ display: 'flex', gap: 16 }}>
                      <Checkbox checked={lang} onChange={(e) => setLang(e.target.checked)}>Translate</Checkbox>
                      <Checkbox checked={status} onChange={(e) => setStatus(e.target.checked)}>Augment</Checkbox>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.04em', color: '#667085' }}>SUBMISSION TASK</div>
                    <Select value={selectAns} onChange={(v) => setSelectAns(v)}
                      options={[{ value: 'kis', label: 'KIS' }, { value: 'qa', label: 'QA' }]} />
                  </div>
                }
              >
                <Button icon={<SlidersOutlined />}>Nâng cao</Button>
              </Popover>
              <Button
                type="primary"
                icon={<MdManageSearch size={16} />}
                onClick={async (e) => { e.preventDefault(); await handleSearchClick(screen1 !== '' || screen2 !== ''); }}
              >
                Tìm kiếm
              </Button>
            </div>

            {/* Modality chips */}
            <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap' }}>
              {[['visual', 'Visual'], ['caption', 'Caption']].map(([v, label]) => (
                <button key={v} className={searchMode === v ? 'chip chip-active' : 'chip'} onClick={() => setSearchMode(v)}>{label}</button>
              ))}

              {/* ASR chip -> popover (OCR only / Hybrid) */}
              <Popover
                open={asrPopOpen}
                onOpenChange={setAsrPopOpen}
                trigger="click"
                placement="bottom"
                content={
                  <div style={{ width: 260, display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <Radio.Group value={asrChipMode} onChange={(e) => setAsrChipMode(e.target.value)} optionType="button" buttonStyle="solid" size="small">
                      <Radio.Button value="only">ASR only</Radio.Button>
                      <Radio.Button value="hybrid">Hybrid</Radio.Button>
                    </Radio.Group>
                    <span style={{ fontSize: 12, color: '#64748B' }}>
                      {asrChipMode === 'hybrid' ? 'Lọc kết quả semantic (Top-K) theo lời nói khớp query.' : 'Tìm trực tiếp theo lời nói (ASR).'}
                    </span>
                    <Input.TextArea rows={2} value={asrHyQuery} onChange={(e) => setAsrHyQuery(e.target.value)} placeholder="Nội dung lời nói cần tìm…" />
                    <Button type="primary" size="small" block onClick={() => runChip('asr')}>Áp dụng</Button>
                  </div>
                }
              >
                <button className={(searchMode === 'asr' || asrHyOn) ? 'chip chip-active' : 'chip'}>{chipLabel('ASR', asrChipMode, asrHyOn)}</button>
              </Popover>

              {/* OCR chip -> popover (OCR only / Hybrid) */}
              <Popover
                open={ocrPopOpen}
                onOpenChange={setOcrPopOpen}
                trigger="click"
                placement="bottom"
                content={
                  <div style={{ width: 260, display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <Radio.Group value={ocrChipMode} onChange={(e) => setOcrChipMode(e.target.value)} optionType="button" buttonStyle="solid" size="small">
                      <Radio.Button value="only">OCR only</Radio.Button>
                      <Radio.Button value="hybrid">Hybrid</Radio.Button>
                    </Radio.Group>
                    <span style={{ fontSize: 12, color: '#64748B' }}>
                      {ocrChipMode === 'hybrid' ? 'Lọc kết quả semantic (Top-K) theo chữ hiển thị (OCR) khớp query.' : 'Tìm trực tiếp theo chữ trên màn hình (OCR).'}
                    </span>
                    <Input.TextArea rows={2} value={ocrHyQuery} onChange={(e) => setOcrHyQuery(e.target.value)} placeholder="Chữ cần tìm…" />
                    <Button type="primary" size="small" block onClick={() => runChip('ocr')}>Áp dụng</Button>
                  </div>
                }
              >
                <button className={(searchMode === 'ocr' || ocrHyOn) ? 'chip chip-active' : 'chip'}>{chipLabel('OCR', ocrChipMode, ocrHyOn)}</button>
              </Popover>

              {/* Objects chip -> popover (traffic detseg filter) */}
              <Popover
                open={objPopOpen}
                onOpenChange={(o) => { setObjPopOpen(o); if (o) setSearchMode('traffic'); }}
                trigger="click"
                placement="bottom"
                content={trafficPanel}
              >
                <button className={searchMode === 'traffic' ? 'chip chip-active' : 'chip'}>
                  Objects
                  {trafObjects.filter((o) => o.name).length > 0 && (
                    <span style={{
                      marginLeft: 6, fontSize: 11, fontWeight: 700, minWidth: 16, height: 16,
                      padding: '0 4px', borderRadius: 999, display: 'inline-flex', alignItems: 'center',
                      justifyContent: 'center', background: '#1677FF', color: '#fff',
                    }}>{trafObjects.filter((o) => o.name).length}</span>
                  )}
                </button>
              </Popover>

              <button className={searchMode === 'trake' ? 'chip chip-active' : 'chip'} onClick={() => setSearchMode('trake')}>TRAKE</button>
            </div>
          </div>

          {/* Result area */}
          <div style={{ marginTop: 20 }}>
            {searchMode === "trake" ? (
              <TrakePanel
                language={lang === true}
                model={model}
                onSubmitCombo={({ videoId, frameIds }) => {
                  setInf({ taskType: 'trake', video_id: videoId, frameIds })
                  setAnsflag(true)
                }}
              />
            ) : asrActive ? (
              <AsrResults
                loading={asrLoading}
                error={asrError}
                results={asrResults}
                onSubmitFrame={(f) => {
                  // Millisecond lấy từ frame_stamp (timestamp thật), KHÔNG suy từ frame_id/fps (fps N không cố định).
                  const t = Number(f.frame_stamp)
                  const mstime = Number.isFinite(t) ? Math.round(t * 1000) : 0
                  setInf({ video_id: f.video_id, L: f.L, V: f.V, frame_id: f.frame_id, fps: f.fps, frame_stamp: f.frame_stamp, mstime })
                  setAnsflag(true)
                }}
              />
            ) : retrival.length > 0 ? (
              <>
                <div className="result-filter-bar">
                  <span className="result-filter-count">
                    Hiển thị {filteredRetrival.length}/{retrival.length} kết quả
                  </span>
                  {/* Chip filter Objects đang áp — bấm × để bỏ & tìm lại */}
                  {trafObjects.map((o, i) => o.name ? (
                    <span key={`ofc-${i}`} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600,
                      padding: '2px 6px 2px 10px', borderRadius: 999, background: '#EFF6FF',
                      border: '1px solid #BFDBFE', color: '#1677FF',
                    }}>
                      Objects: {o.name}{o.min > 1 ? ` ≥${o.min}` : ''}
                      <button onClick={() => { setTrafObj(i, 'name', ''); runTrafficSearch(); }}
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#1677FF', fontSize: 13, lineHeight: 1, padding: 0 }}>×</button>
                    </span>
                  ) : null)}
                  <Select
                    size="small"
                    value={sortBy}
                    onChange={(v) => { setSortBy(v); setPage(1); }}
                    style={{ width: 168, marginLeft: 'auto' }}
                    options={[{ value: 'relevance', label: 'Sắp xếp: Độ liên quan' }, { value: 'time', label: 'Sắp xếp: Thời gian' }]}
                  />
                  <Select
                    mode="multiple"
                    allowClear
                    className="result-filter-select"
                    placeholder="Chọn một hoặc nhiều bộ L"
                    value={filterLs}
                    onChange={(values) => {
                      setFilterLs(values);
                      setFilterVs([]);
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
                    mode="multiple"
                    allowClear
                    className="result-filter-select"
                    placeholder="V chỉ thu hẹp bộ L có video đó"
                    value={filterVs}
                    onChange={(values) => { setFilterVs(values); setPage(1); }}
                  >
                    {availableVs.map((value) => (
                      <Option key={value} value={value}>V{value}</Option>
                    ))}
                  </Select>
             
                  <Select
                    mode="multiple"
                    allowClear
                    showSearch
                    className="result-filter-select result-exclude-select"
                    placeholder="Lọc bỏ L hoặc L_V"
                    value={excludedScopes}
                    onChange={(values) => { setExcludedScopes(values); setPage(1); }}
                  >
                    {availableLs.map((value) => (
                      <Option key={`l:${value}`} value={`l:${value}`}>
                        Bỏ toàn bộ {Number(value) <= 20 ? 'K' : 'L'}{value}
                      </Option>
                    ))}
                    {availableVideoPairs.map(({ L, V }) => (
                      <Option key={`lv:${L}:${V}`} value={`lv:${L}:${V}`}>
                        Bỏ {Number(L) <= 20 ? 'K' : 'L'}{L}_V{V}
                      </Option>
                    ))}
                  </Select>
                  <Checkbox checked={keepFilters} onChange={(event) => setKeepFilters(event.target.checked)}>
                    Giữ bộ lọc khi tìm kiếm mới
                  </Checkbox>
                  <Button size="small" onClick={clearResultFilters}>Xóa bộ lọc</Button>
                </div>
                {filteredRetrival.length === 0 ? (
                  <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Không có kết quả phù hợp với bộ lọc L/V.</div>
                ) : (
                  <>
                    <div className="result-grid">
                      {pagedRetrival.map((item, i) => renderResultCard(item, (page - 1) * pageSize + i))}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 20 }}>
                      <Pagination
                        current={page}
                        pageSize={pageSize}
                        total={filteredRetrival.length}
                        showSizeChanger
                        pageSizeOptions={[12, 24, 48, 96]}
                        onChange={(p, ps) => { setPage(p); setPageSize(ps); }}
                      />
                    </div>
                  </>
                )}
              </>
            ) : (
              <div style={{
                width: '100%', minHeight: 420, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 6, textAlign: 'center',
              }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 16, marginBottom: 8,
                  background: '#EFF6FF', color: '#1677FF',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <MdManageSearch size={30} />
                </div>
                <h2 style={{ fontSize: 20, fontWeight: 700, color: '#0F2747', margin: 0 }}>Bắt đầu tìm kiếm</h2>
                <p style={{ color: '#64748B', margin: 0 }}>Tìm bằng văn bản, hình ảnh, giọng nói (ASR), chữ trên màn hình (OCR) hoặc lọc giao thông.</p>
                <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
                  {['xe máy chạy qua xe buýt xanh', 'người mặc áo đỏ ở ngã tư', 'giải đua xe đạp cúp truyền hình'].map((ex) => (
                    <button key={ex} className="chip" onClick={() => { setSearchMode('visual'); setScreen1(ex); }}>“{ex}”</button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      {mondalFLag && (
        <Infor
          setModalFlag={setModalFlag}
          selectedFrame={selectedFrame}
          onSubmitSingle={(draft) => {
            setInf(draft)
            setAnsflag(true)
          }}
        />
      )}
      {ytflag && (
        <YoutubePlayer
          url={vidFlag}

          close={setYtflag}
        />
      )}
      <SubmissionModal
        open={ansflag}
        onClose={() => setAnsflag(false)}
        draft={inf}
        defaultTaskType={searchMode === 'trake' ? 'trake' : selectAns}
      />

      {/* Video Result Inspector — Frame → Score → Metadata → Why matched → Content → Actions */}
      <Drawer
        open={!!detailItem}
        onClose={() => setDetailItem(null)}
        placement="right"
        width={448}
        title="Chi tiết frame"
        styles={{ body: { padding: 0, background: '#F8FAFC' } }}
      >
        {detailItem && (() => {
          const it = { ...detailItem, ...(detailMeta || {}) }; // gộp metadata tra thêm từ Mongo
          let pathVal = it.path || it.url || "";
          const imageUrl = pathVal ? (String(pathVal).startsWith("http") ? pathVal : `/frames/${String(pathVal).replace(/^\/+/, '')}`) : null;
          const videoId = it.video_id || "";
          const L = it.L ?? "";
          const V = it.V ?? "";
          const frame_id = it.frame_id ?? "";
          const url = it.video_url || "";
          const time = Number(it.frame_stamp ?? it.t_start ?? 0) || 0;
          const mstime = Math.round(time * 1000);
          const fps = it.fps ?? "";
          const minute = Math.floor(time / 60);
          const sec = Math.floor(time - 60 * minute);
          const mmss = `${String(minute).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
          const caption = it.caption || "";
          const ocrText = it.ocr_text || "";
          const asrText = (!it.ocr_text && !it.caption) ? (it.text || "") : (it.asr_text || "");
          const score = typeof it.score === "number" ? it.score : null;
          const counts = it.counts && typeof it.counts === "object" ? it.counts : null;
          const isBatch2 = /^[NSM]/i.test(String(videoId)) || String(videoId).includes('-');
          const videoLabel = isBatch2 ? videoId : `${L ? (parseInt(String(L).slice(0, 2)) <= 20 ? "K" : "L") + L : videoId}${V ? " · V" + V : ""}`;

          // Matched modalities (chỉ dựa trên dữ liệu thực có). Màu tiết chế: modality = xanh, Hybrid = accent đậm.
          const matched = [];
          if (score != null) matched.push('Visual');
          if (searchMode === 'caption' || caption) matched.push('Caption');
          if (ocrHyOn && ocrHyQuery.trim()) matched.push('OCR · Hybrid');
          else if (searchMode === 'ocr') matched.push('OCR');
          if (asrHyOn && asrHyQuery.trim()) matched.push('ASR · Hybrid');
          else if (searchMode === 'asr') matched.push('ASR');
          if (counts) matched.push('Objects');

          // highlight đoạn text trùng query (trung thực: chỉ đánh dấu chỗ khớp thật, không bịa điểm)
          const highlight = (text, q) => {
            if (!q) return text;
            const i = String(text).toLowerCase().indexOf(q.toLowerCase());
            if (i < 0) return text;
            return (<>{String(text).slice(0, i)}<mark style={{ background: '#FEF3C7', color: '#92400E', padding: '0 2px', borderRadius: 3 }}>{String(text).slice(i, i + q.length)}</mark>{String(text).slice(i + q.length)}</>);
          };
          const Label = ({ children }) => (
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.06em', color: '#94A3B8', textTransform: 'uppercase', margin: '4px 0 8px' }}>{children}</div>
          );
          const Divider = () => <div style={{ height: 1, background: '#EAECF0', margin: '4px 0' }} />;

          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 16 }}>
              {/* FRAME + overlay */}
              <div style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', background: '#0F2747', aspectRatio: '16/9', boxShadow: '0 1px 3px rgba(16,24,40,.12)' }}>
                {imageUrl
                  ? <img src={imageUrl} alt="frame" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
                  : <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8' }}>No preview</div>}
                <span style={{ position: 'absolute', left: 10, bottom: 10, background: 'rgba(15,39,71,.85)', color: '#fff', fontSize: 12, fontWeight: 600, padding: '3px 9px', borderRadius: 6 }}>▶ {mmss}</span>
                {score != null && <span style={{ position: 'absolute', right: 10, top: 10, background: 'rgba(22,119,255,.95)', color: '#fff', fontSize: 13, fontWeight: 700, padding: '3px 9px', borderRadius: 6 }}>{score.toFixed(2)}</span>}
              </div>

              {/* Metadata gọn */}
              <div>
                <div style={{ fontWeight: 700, fontSize: 19, color: '#0F2747', lineHeight: 1.1 }}>{videoLabel}</div>
                <div style={{ color: '#64748B', fontSize: 13, marginTop: 3 }}>
                  Frame {frame_id} · {mmss}{fps !== "" && fps != null ? ` · ${fps} FPS` : ""}
                </div>
              </div>

              {/* Độ tương đồng (score thật từ Qdrant) */}
              {score != null && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, color: '#64748B' }}>Độ tương đồng</span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: '#1677FF' }}>{score.toFixed(2)}</span>
                  </div>
                  <div style={{ height: 8, borderRadius: 999, background: '#EEF2F7', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.max(0, Math.min(1, score)) * 100}%`, background: 'linear-gradient(90deg,#1677FF,#4096FF)', borderRadius: 999 }} />
                  </div>
                </div>
              )}

              {/* MATCHED BY */}
              {matched.length > 0 && (
                <div>
                  <Label>Matched by</Label>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {matched.map((m) => {
                      const hy = m.includes('Hybrid');
                      return (
                        <span key={m} style={{
                          fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 999,
                          border: `1px solid ${hy ? '#1677FF' : '#DBE3EE'}`,
                          color: hy ? '#1677FF' : '#475569',
                          background: hy ? '#EFF6FF' : '#F8FAFC',
                        }}>{m}</span>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* CONTENT — chỉ hiện phần có dữ liệu */}
              {caption && (<><Divider /><div><Label>Caption</Label><div style={{ fontSize: 14, color: '#172033', lineHeight: 1.5 }}>{caption}</div></div></>)}
              {ocrText && (<><Divider /><div><Label>OCR{ocrHyOn && ocrHyQuery.trim() ? ' · Hybrid' : ''}</Label><div style={{ fontSize: 14, color: '#172033', lineHeight: 1.5 }}>“{highlight(ocrText, ocrHyOn ? ocrHyQuery.trim() : '')}”</div></div></>)}
              {asrText && (<><Divider /><div><Label>ASR{asrHyOn && asrHyQuery.trim() ? ' · Hybrid' : ''}</Label><div style={{ fontSize: 14, color: '#172033', lineHeight: 1.5 }}>“{highlight(asrText, asrHyOn ? asrHyQuery.trim() : '')}”</div></div></>)}
              {counts && (
                <><Divider /><div>
                  <Label>Objects</Label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => (
                      <span key={k} style={{ fontSize: 13, color: '#334155', background: '#F1F5F9', padding: '3px 10px', borderRadius: 8 }}><b>{v}</b> {k}</span>
                    ))}
                  </div>
                </div></>
              )}

              {/* THÔNG TIN BỔ SUNG */}
              {(() => {
                const info = [];
                info.push(['Video', videoLabel]);
                info.push(['Thời điểm', mmss]);
                if (fps !== "" && fps != null) info.push(['FPS', String(fps)]);
                if (it.vehicle_count != null) info.push(['Số xe', String(it.vehicle_count)]);
                if (it.traffic_density_proxy != null) info.push(['Mật độ', Number(it.traffic_density_proxy).toFixed(2)]);
                return (
                  <><Divider /><div>
                    <Label>Thông tin bổ sung</Label>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {info.map(([k, v]) => (
                        <span key={k} style={{ fontSize: 12, color: '#334155', background: '#F1F5F9', padding: '3px 10px', borderRadius: 8 }}>
                          <span style={{ color: '#94A3B8' }}>{k}:</span> <b>{v}</b>
                        </span>
                      ))}
                    </div>
                    {detailLoading && <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 8 }}>Đang tải metadata…</div>}
                  </div></>
                );
              })()}

              {/* ACTIONS */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
                {url && <Button type="primary" size="large" block icon={<FaCirclePlay />} onClick={() => { setVidFlag(`${url}&t=${time}s`); setYtflag(true); }}>Mở video</Button>}
                <Button block icon={<FaFolderOpen />} onClick={() => {
                  setModalFlag(true);
                  setSelectedFrame({ idx: it.idx, frame_id, L: Number(String(L).replace(/^[KL]/i, '')), V: Number(String(V).replace(/^V/i, '')), video_id: videoId });
                }}>Xem ±10 keyframe</Button>
                <Button type="text" icon={<IoIosAddCircle />} style={{ color: '#1677FF' }} onClick={() => {
                  setInf({ video_id: videoId, L, V, frame_id, fps, frame_stamp: it.frame_stamp, mstime, minute, sec });
                  setAnsflag(true);
                }}>Nộp kết quả này</Button>
              </div>
            </div>
          );
        })()}
      </Drawer>

    </>
  )
}

export default Jobs
