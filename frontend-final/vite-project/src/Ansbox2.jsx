import React, { useState } from 'react'
import "./Infor.css";
import { Button, Input } from 'antd';
import { answer } from './api';

function Ansbox1({inf, close}) {
    const ans = {
        answerSets: [{
            answers: [{
                text: "TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,..."
            }]
        }]
    }
    
    const infor = inf
    const [med, setMed] = useState(`${parseInt(infor.L.slice(0,2)) <= 20 ? "K" : "L"}${infor.L.slice(0,2)}_V${infor.V}`)
    // Sửa lại phần khởi tạo state với frame_id
    const [frameIds, setFrameIds] = useState(() => {
        const initialFrameId = infor.frame_id ? infor.frame_id.toString() : "";
        console.log("Initial frame ID:", initialFrameId); // Debug log
        return [initialFrameId];
    })
    const [anse, setAnse] = useState("")

    // Thêm ô input mới cho frame ID
    const addFrameInput = () => {
        setFrameIds([...frameIds, ""])
    }

    // Hàm chuyển đổi timestamp sang frameId
    const convertTimestampToFrame = (timestamp) => {
        const timestampPattern = /^(\d{1,2}):(\d{1,2})$/;
        const match = timestamp.match(timestampPattern);
        
        if (match) {
            const minutes = parseInt(match[1]);
            const seconds = parseInt(match[2]);
            return Math.round((minutes * 60 + seconds) * infor.fps);
        }
        return null;
    }

    // Cập nhật frame ID không chuyển đổi ngay
    const updateFrameId = (index, value) => {
        const newFrameIds = [...frameIds];
        newFrameIds[index] = value;
        setFrameIds(newFrameIds);
    }

    // Hàm xử lý chuyển đổi chung
    const handleConversion = (index) => {
        const value = frameIds[index];
        const newFrameIds = [...frameIds];
        
        if (/^\d{1,2}:\d{1,2}$/.test(value)) {
            const frameNumber = convertTimestampToFrame(value);
            if (frameNumber !== null) {
                newFrameIds[index] = frameNumber.toString();
                setFrameIds(newFrameIds);
            }
        }
    }

    // Xử lý khi nhấn Enter
    const handleKeyDown = (index, e) => {
        if (e.key === 'Enter') {
            handleConversion(index);
        }
    }

    // Xử lý khi blur
    const handleBlur = (index) => {
        handleConversion(index);
    }

    // Xóa ô input frame ID
    const removeFrameInput = (index) => {
        if (frameIds.length > 1) {
            const newFrameIds = frameIds.filter((_, i) => i !== index)
            setFrameIds(newFrameIds)
        }
    }

    // Lấy danh sách frame IDs đã nhập (loại bỏ các ô trống)
    const getFrameIdsString = () => {
        const validFrameIds = frameIds.filter(id => id && typeof id === 'string' && id.trim() !== '').map(id => id.trim());
        return validFrameIds.join(",");
    }

    return (
        <div className="overlay" style={{ zIndex: 9999 }}>
            <div className="content" style={{ width: "840px", height: "660px", overflowY: 'auto' }}>
                <Button
                    style={{ alignSelf: "flex-end" }}
                    onClick={() => close(false)}
                >
                    Close
                </Button>
                <p>{`${parseInt(infor.L.slice(0,2)) <= 20 ? "K" : "L"}${infor.L.slice(0,2)}_V${infor.V}`}</p>
                <p>{`${infor.mstime}`}</p>
                <div>{`${parseInt(infor.L.slice(0,2)) <= 20 ? "K" : "L"}: ${infor.L.slice(0,2)}${infor.V ? " - V: " + infor.V : ""} ${infor.frame_id ? "- " +infor.frame_id : ""} - ${infor.minute}m${infor.sec.toFixed(0)}s ${infor.fps} `} </div>
                
                <Input
                    style={{ width: '320px', borderRadius: 8, marginBottom: '20px' }}
                    placeholder="Video_ID"
                    value={med}
                    onChange={(e) => {
                        setMed(e.target.value)
                    }}
                />

                {/* Phần quản lý multiple frame IDs */}
                <div style={{ marginBottom: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                        <h4 style={{ margin: '0 10px 0 0' }}>Frame IDs:</h4>
                        <Button 
                            type="primary" 
                            size="small" 
                            onClick={addFrameInput}
                            style={{ marginRight: '10px' }}
                        >
                            + Thêm Frame
                        </Button>
                    </div>
                    
                    {frameIds.map((frameId, index) => (
                        <div key={index} style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                            <Input
                                style={{ width: '280px', borderRadius: 8, marginRight: '8px' }}
                                placeholder={`Frame_ID ${index + 1} (number or mm:ss)`}
                                value={frameId}
                                onChange={(e) => updateFrameId(index, e.target.value)}
                                onKeyDown={(e) => handleKeyDown(index, e)}
                                onBlur={() => handleBlur(index)}
                            />
                            <Button 
                                type="link" 
                                danger 
                                onClick={() => removeFrameInput(index)}
                                disabled={frameIds.length === 1}
                            >
                                Xóa
                            </Button>
                        </div>
                    ))}
                </div>

                <Button onClick={async (e) => {
                    const frameIdsString = getFrameIdsString()
                    ans.answerSets[0].answers[0].text = `TR-${med}-${frameIdsString}`
                    console.log(ans)
                    e.preventDefault();
                    const resp = await answer(ans)
                    const result = resp?.data
                    console.log(result)
                }}>
                    <p>Nộp nha ku</p>
                </Button>

            </div>
        </div>
    )
}

export default Ansbox1