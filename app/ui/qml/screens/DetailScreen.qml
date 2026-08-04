import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.sectionGap

    AppHeader {
        showBrand: false
        title: "Product"
        showCart: false
        Layout.fillWidth: true
    }

    ElevatedCard {
        Layout.fillWidth: true
        Layout.preferredHeight: 280
        visible: Theme.productImageTreatment !== "none"

        Item {
            anchors.fill: parent
            anchors.margins: 12

            Rectangle {
                anchors.fill: parent
                radius: Theme.cornerRadius - 4
                color: Theme.imageWell
                clip: true

                Image {
                    anchors.fill: parent
                    anchors.margins: 12
                    source: App.detailImageUrl
                    fillMode: Theme.productImageTreatment === "cover_rounded"
                               ? Image.PreserveAspectCrop
                               : Image.PreserveAspectFit
                    asynchronous: true
                    visible: App.detailImageUrl.length > 0
                }

                Text {
                    anchors.centerIn: parent
                    visible: App.detailImageUrl.length === 0
                    text: App.detailSlotId
                    color: Theme.primary
                    font.family: Theme.fontFamily
                    font.pixelSize: 56
                    font.bold: true
                }
            }
        }
    }

    Text {
        text: App.detailName
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx - 4
        font.bold: true
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    PriceDisplay {
        amount: App.detailPriceText
        Layout.fillWidth: true
    }

    Text {
        text: App.detailMeta
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodyFontPx + 1
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    QuantityControl {
        quantity: App.detailQty
        Layout.fillWidth: true
        onDecrement: App.detailAdjust(-1)
        onIncrement: App.detailAdjust(1)
    }

    Item { Layout.fillHeight: true }

    BottomActionBar {
        Layout.fillWidth: true
        SecondaryButton {
            text: "Back"
            Layout.fillWidth: true
            onClicked: App.backToBrowse()
        }
        PrimaryButton {
            text: "Add to cart"
            Layout.fillWidth: true
            onClicked: App.detailAdd()
        }
    }
}
