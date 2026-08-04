import QtQuick
import QtQuick.Layouts

ElevatedCard {
    id: root
    property string name: ""
    property int quantity: 1
    property string lineTotalText: ""

    implicitHeight: row.implicitHeight + 36
    width: parent ? parent.width : 400

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: root.name
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.subtitleFontPx - 2
                font.bold: true
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Text {
                text: "Qty " + root.quantity
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
            }
        }

        Text {
            text: root.lineTotalText
            color: Theme.price
            font.family: Theme.fontFamily
            font.pixelSize: Theme.priceFontPx - 2
            font.bold: true
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
