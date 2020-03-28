// This script populates bogging-table with data in polls/bogging.html

var bogging_table = new Tabulator("#bogging-table",
  {
    data:tabledata,          // Assign data to table
    layout:"fitDataStretch", // Fit columns to width of table, stretch last col
    columns:[                // Define table columns
      {formatter:"rowSelection", titleFormatter:"rowSelection", align:"center", headerSort:false, cellClick:(e, cell) => {cell.getRow().toggleSelect();}},
      {title:"Date",               field:"Date",               align:"center"},
      {title:"Percent",            field:"Percent",            align:"center"},
      {title:"3 Day Percent",      field:"3 Day Percent",      align:"center", topCalc:"avg"},
      {title:"3 Day Open Percent", field:"3 Day Open Percent", align:"center", topCalc:"avg"},
      {title:"Headline",           field:"Headline",           align:"center",width:400, formatter:"link",
      formatterParams:{labelField:"Headline", urlField:'URL'}},
      {title:"Category",           field:"Category",           align:"center"},
    ],
  });

$("#del-row").click(() => {
  bogging_table.deleteRow(bogging_table.getSelectedRows());
});

$("#reset").click(() => {
  bogging_table.setData(tabledata);
});