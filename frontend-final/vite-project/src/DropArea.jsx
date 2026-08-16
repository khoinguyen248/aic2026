import React, { useEffect, useState } from "react";

export default function DropArea({ droppedItems, onDrop, onRemove , onStateChange}) {
  const [objectState, setObjectState] = useState([]);
  const colLabels = ["a", "b", "c", "d", "e", "f", "g"];

  const handleAdd = (obj) => {
    setObjectState((prev) => [...prev, obj]);
  };

  const handleRemove = (key) => {
    setObjectState((prev) => prev.filter((v) => v.key !== key));
  };

  // Gom nhóm thành string mong muốn
  const groupedString =  
  Object.values(
    objectState.reduce((acc, item) => {
      if (!acc[item.label]) acc[item.label] = [];
      acc[item.label].push(item.key);
      return acc;
    }, {})
  )
    .map((arr) => arr.join(" "))
    .join(", ") 



  useEffect(() => {
    console.log(groupedString);
    if (onStateChange) {
     onStateChange(groupedString);
   }

  }, [groupedString, onStateChange]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "repeat(7, 1fr)",
        gridTemplateColumns: "repeat(7, 1fr)",
        width: "280px",
        height: "300px",
        border: "2px solid black",
      }}
    >
      {Array.from({ length: 49 }).map((_, index) => {
        const row = Math.floor(index / 7);
        const col = index % 7;
        const colLabel = colLabels[col];

        const itemInCell = droppedItems.find(
          (item) => item.position.row === row && item.position.col === colLabel
        );

        const handleCellDrop = (e) => {
          e.preventDefault();
          const data = e.dataTransfer.getData("item");
          if (data) {
            const item = JSON.parse(data);
            const itemKey = `${colLabel}${row}${item.label}`;
            onDrop(item, { row, col: colLabel });
            handleAdd({ key: itemKey, label: item.label });
          }
        };

        return (
          <div
            key={`${row}-${col}`}
            onDrop={handleCellDrop}
            onDragOver={(e) => e.preventDefault()}
            style={{
              borderRight: col === 6 ? "none" : "1px dashed grey",
              borderBottom: row === 6 ? "none" : "1px dashed grey",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
            }}
          >
            {itemInCell && (
              <>
                <span
                  title={`${colLabel}${row}${itemInCell.label}`}
                >
                   <img title={`${itemInCell.label}`} src={`/icons_img/${itemInCell.label}.png`} alt="" style={{width:'20px', height:'20px'}}/>
                </span>
                <button
                  onClick={() => {
                    onRemove(droppedItems.indexOf(itemInCell));
                    handleRemove(`${colLabel}${row}${itemInCell.label}`);
                  }}
                  style={{
                    position: "absolute",
                    top: "2px",
                    right: "2px",
                    fontSize: "12px",
                    border: "none",
                    background: "red",
                    color: "white",
                    cursor: "pointer",
                  }}
                >
                  x
                </button>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
