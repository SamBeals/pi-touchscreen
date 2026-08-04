import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    anchors.fill: parent
    spacing: Theme.sectionGap

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: Theme.productImageTreatment === "none" ? 0 : 240
        visible: Theme.productImageTreatment !== "none"

        Rectangle {
            anchors.fill: parent
            radius: Theme.productImageTreatment === "circle" ? width / 2 : Theme.cornerRadius
            color: Theme.surface
            clip: true

            Image {
                anchors.fill: parent
                source: App.detailImageUrl
                fillMode: Theme.productImageTreatment === "contain" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                asynchronous: true
                visible: App.detailImageUrl.length > 0
            }
        }
    }

    Text {
        text: App.detailName
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
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
        font.pixelSize: Theme.subtitleFontPx
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
            success: true
            Layout.fillWidth: true
            onClicked: App.detailAdd()
        }
    }
}
