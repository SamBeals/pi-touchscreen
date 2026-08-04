import QtQuick
import SellMate 1.0

Text {
    id: root
    property string amount: ""
    text: amount
    color: Theme.price
    font.family: Theme.fontFamily
    font.pixelSize: Theme.priceFontPx
    font.bold: true
    wrapMode: Text.WordWrap
    visible: text.length > 0
}
