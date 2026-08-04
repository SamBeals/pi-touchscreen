import QtQuick
import QtQuick.Layouts
import SellMate 1.0

Item {
    id: root
    property string slotId: ""
    property string name: ""
    property string priceText: ""
    property string stockText: ""
    property string imageUrl: ""
    property int qty: 0

    ElevatedCard {
        id: card
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            // Image / slot placeholder — square-ish media area
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: 140
                Layout.minimumHeight: 120

                Rectangle {
                    anchors.fill: parent
                    radius: Math.max(12, Theme.cornerRadius - 4)
                    color: Theme.imageWell
                    clip: true

                    Image {
                        anchors.fill: parent
                        anchors.margins: 8
                        source: root.imageUrl
                        fillMode: Theme.productImageTreatment === "cover_rounded"
                                   ? Image.PreserveAspectCrop
                                   : Image.PreserveAspectFit
                        asynchronous: true
                        visible: root.imageUrl.length > 0
                    }

                    // Slot-ID placeholder when no image
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        visible: root.imageUrl.length === 0
                        width: parent.width - 16

                        Text {
                            width: parent.width
                            text: root.slotId
                            color: Theme.primary
                            font.family: Theme.fontFamily
                            font.pixelSize: Math.min(48, parent.width * 0.28)
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }

            Text {
                text: root.slotId
                color: Theme.primary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
                font.bold: true
                visible: root.imageUrl.length > 0
                Layout.fillWidth: true
            }

            Text {
                text: root.name
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx + 1
                font.bold: true
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            PriceDisplay {
                amount: root.priceText
                Layout.fillWidth: true
            }

            Text {
                visible: root.qty > 0 && root.qty <= 3
                text: root.qty === 1 ? "Only 1 left" : "Only " + root.qty + " left"
                color: Theme.warning
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx - 2
                Layout.fillWidth: true
            }
        }
    }

    // Entire card is the hit target
    MouseArea {
        anchors.fill: parent
        onClicked: {
            App.bumpIdle()
            App.openDetail(root.slotId)
        }
        onPressed: card.scale = 0.98
        onReleased: card.scale = 1.0
        onCanceled: card.scale = 1.0
    }

    Behavior on opacity {
        NumberAnimation { duration: Theme.animationMs }
    }
}
