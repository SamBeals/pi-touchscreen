import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string slotId: ""
    property string name: ""
    property string priceText: ""
    property string stockText: ""
    property string imageUrl: ""

    radius: Theme.cornerRadius
    color: Theme.surface
    border.width: Theme.productCardStyle === "outlined" ? 1 : 0
    border.color: Theme.secondary
    implicitHeight: Math.max(Theme.cardMinHeight, content.implicitHeight + 32)

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Item {
            visible: Theme.productImageTreatment !== "none"
            Layout.fillWidth: true
            Layout.preferredHeight: imageUrl.length > 0 || Theme.productImageTreatment !== "none" ? 140 : 0

            Rectangle {
                anchors.fill: parent
                radius: Theme.productImageTreatment === "circle" ? width / 2 : Theme.cornerRadius
                color: Theme.background
                clip: true

                Image {
                    anchors.fill: parent
                    source: root.imageUrl
                    fillMode: Theme.productImageTreatment === "contain" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                    asynchronous: true
                    visible: root.imageUrl.length > 0
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.imageUrl.length === 0
                    text: "No image"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodyFontPx
                }
            }
        }

        Text {
            text: root.name
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.subtitleFontPx
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        PriceDisplay {
            amount: root.priceText
            Layout.fillWidth: true
        }

        Text {
            text: root.stockText
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodyFontPx
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Item { Layout.fillHeight: true }

        PrimaryButton {
            text: "View"
            Layout.fillWidth: true
            onClicked: App.openDetail(root.slotId)
        }
    }
}
