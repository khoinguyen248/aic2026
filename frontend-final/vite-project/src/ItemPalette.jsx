import React from 'react';

export default function ItemPalette({ items }) {
  const handleDragStart = (e, item) => {
    e.dataTransfer.setData('item', JSON.stringify(item));
  };

  return (
    <div style={{
      border: 'none',
      padding: '10px',
      width: '260px'
    }}>
      <h4>Objects & colors of the scene</h4>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
        {items.map((item) => (
          <div
            key={item.id}
            draggable
            onDragStart={(e) => handleDragStart(e, item)}
            style={{
              border: 'none',
              padding: 'none',
              textAlign: 'center',
              cursor: 'grab',
            }}
          >
            {/* <div style={{height:'20px', width:'30px'}}>{`${item.icon}`}</div> */}
           <img title={`${item.label}`} src={`/icons_img/${item.label}.png`} alt="" style={{width:'30px', height:'30px'}}/>
          </div>
        ))}
      </div>
    </div>
  );
}
